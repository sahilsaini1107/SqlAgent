"""Deterministic SQL validation gate.

Runs after every generation/repair/optimization. No LLM is involved. The order is cheapest
and most decisive first: parse -> single statement -> read-only -> functions -> schema binding
-> joins -> re-validate the serialized SQL -> real-engine EXPLAIN. Errors block the query;
warnings are advisory. The EXPLAIN backstop is mandatory, so unknown columns/syntax a static
check can't resolve are still caught by the engine before any SQL is returned.

This is one half of "the LLM proposes, code decides" — the other half is the read-only
database layer, which independently enforces safety even if a
bug here let something through.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import cast

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.domain.query_policy import ALLOWED_FUNCTIONS
from app.domain.schema_catalog import SchemaCatalog
from app.domain.validation import ValidationIssue, ValidationResult

# Any of these node types appearing ANYWHERE in the tree means the statement is not a pure
# read. DML/DDL are sqlglot's abstract bases for data/schema-modifying statements and Command
# catches engine statements it doesn't model structurally (PRAGMA, VACUUM, REINDEX, ...), so
# the three bases alone cover the space; the explicit names are belt-and-suspenders. We resolve
# every name up front and raise at import if sqlglot ever drops one — a silent ``hasattr`` skip
# would quietly remove a guard on a dependency bump.
_FORBIDDEN_NAMES = [
    "DML", "DDL", "Command", "Insert", "Update", "Delete", "Merge", "Drop", "Create", "Alter",
    "TruncateTable", "Pragma", "Attach", "Detach", "Transaction", "Commit", "Rollback",
    "Set", "Use", "Copy", "Grant", "Analyze",
]
_missing = [name for name in _FORBIDDEN_NAMES if not hasattr(exp, name)]
if _missing:  # pragma: no cover - guards against a sqlglot upgrade silently weakening the gate
    raise RuntimeError(f"sqlglot is missing expected forbidden expression types: {_missing}")
_FORBIDDEN_TYPES = tuple(getattr(exp, name) for name in _FORBIDDEN_NAMES)

_ALLOWED_ROOT_NAMES = ["Select", "Union", "Intersect", "Except", "Subquery"]
_ALLOWED_ROOTS = tuple(getattr(exp, name) for name in _ALLOWED_ROOT_NAMES if hasattr(exp, name))

# Functions that are never legitimate in a read-only query and must be blocked regardless of
# how sqlglot parses them (dedicated node or Anonymous). The positive allowlist governs unknown
# functions; this denylist is a hard floor for known-dangerous ones.
_FORBIDDEN_FUNCTION_NAMES = frozenset(
    {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer", "zipfile", "lsmode"}
)


@dataclass
class _Binding:
    alias_to_table: dict[str, str] = field(default_factory=dict)
    base_tables: list[str] = field(default_factory=list)
    derived_aliases: set[str] = field(default_factory=set)


class SqlValidator:
    def __init__(
        self,
        catalog: SchemaCatalog,
        *,
        dialect: str = "sqlite",
        allowed_functions: frozenset[str] = ALLOWED_FUNCTIONS,
        execute_check: Callable[[str], None],
    ) -> None:
        self._catalog = catalog
        self._dialect = dialect
        self._allowed_functions = allowed_functions
        self._execute_check = execute_check
        self._fk_pairs = _foreign_key_pairs(catalog)

    def validate(self, sql: str) -> ValidationResult:
        try:
            statements = [s for s in sqlglot.parse(sql, read=self._dialect) if s is not None]
        except SqlglotError as err:
            return ValidationResult([ValidationIssue("PARSE_ERROR", str(err))])

        if not statements:
            return ValidationResult([ValidationIssue("PARSE_ERROR", "No SQL statement found.")])
        if len(statements) > 1:
            return ValidationResult(
                [ValidationIssue("MULTI_STATEMENT", "Only a single statement is allowed.")]
            )

        expr = cast(exp.Expression, statements[0])

        read_only_issues = self._check_read_only(expr)
        if read_only_issues:
            # Do not bind or run a statement that is not a read-only query.
            return ValidationResult(read_only_issues)

        issues: list[ValidationIssue] = []
        issues += self._check_functions(expr)
        binding = self._bind(expr, issues)
        issues += self._check_columns(expr, binding)
        issues += self._check_joins(expr, binding)

        result = ValidationResult(issues)
        if result.passed:
            final_sql = expr.sql(dialect=self._dialect, pretty=True)
            # Validate the exact string that will execute: re-parse the serialized SQL and
            # re-run the read-only gate, so no normalization quirk in sqlglot's roundtrip can
            # re-introduce a write/admin construct past the checks above.
            if recheck := self._recheck_serialized(final_sql):
                return ValidationResult(issues + recheck)
            try:
                self._execute_check(final_sql)
            except Exception as err:  # engine is the final arbiter of syntax/columns
                issues.append(ValidationIssue("EXECUTION_ERROR", _clean(str(err))))
                return ValidationResult(issues)
            return ValidationResult(issues, final_sql=final_sql)
        return result

    def _recheck_serialized(self, final_sql: str) -> list[ValidationIssue]:
        try:
            reparsed = sqlglot.parse_one(final_sql, read=self._dialect)
        except SqlglotError:
            return [ValidationIssue("PARSE_ERROR", "Serialized query could not be re-parsed.")]
        if reparsed is None:
            return [ValidationIssue("PARSE_ERROR", "Serialized query is empty.")]
        return self._check_read_only(cast(exp.Expression, reparsed))

    # -- checks -----------------------------------------------------------------

    def _check_read_only(self, expr: exp.Expression) -> list[ValidationIssue]:
        if not isinstance(expr, _ALLOWED_ROOTS):
            return [
                ValidationIssue(
                    "FORBIDDEN_OPERATION",
                    "Only read-only SELECT queries are allowed.",
                )
            ]
        if list(expr.find_all(*_FORBIDDEN_TYPES)):
            return [
                ValidationIssue(
                    "FORBIDDEN_OPERATION",
                    "The query contains a write or administrative statement, which is not allowed.",
                )
            ]
        for select in expr.find_all(exp.Select):
            if select.args.get("into") is not None:
                return [
                    ValidationIssue("FORBIDDEN_OPERATION", "SELECT ... INTO is not allowed.")
                ]
        return []

    def _check_functions(self, expr: exp.Expression) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        # Walk every function node (not only Anonymous): the denylist must catch a dangerous
        # function even when sqlglot parses it into a dedicated class.
        for fn in expr.find_all(exp.Func):
            names = _function_names(fn)
            forbidden = names & _FORBIDDEN_FUNCTION_NAMES
            if forbidden:
                issues.append(
                    ValidationIssue(
                        "FORBIDDEN_FUNCTION", f"Function '{sorted(forbidden)[0]}' is not allowed."
                    )
                )
                continue
            # Unknown functions (parsed as Anonymous) must be on the positive allowlist.
            if isinstance(fn, exp.Anonymous):
                name = (fn.name or "").lower()
                if name and name not in self._allowed_functions:
                    issues.append(
                        ValidationIssue(
                            "UNSUPPORTED_FUNCTION", f"Function '{name}' is not allowed."
                        )
                    )
        return issues

    def _bind(self, expr: exp.Expression, issues: list[ValidationIssue]) -> _Binding:
        binding = _Binding()
        cte_names = {c.alias_or_name.lower() for c in expr.find_all(exp.CTE)}
        binding.derived_aliases |= cte_names
        for sub in expr.find_all(exp.Subquery):
            if sub.alias:
                binding.derived_aliases.add(sub.alias.lower())

        for table in expr.find_all(exp.Table):
            name = table.name
            key = (table.alias or name).lower()
            if name.lower() in cte_names:
                binding.derived_aliases.add(key)
                continue
            resolved = self._catalog.get_table(name)
            if resolved is None:
                issues.append(
                    ValidationIssue("UNKNOWN_TABLE", f"Unknown table '{name}'.")
                )
                continue
            binding.base_tables.append(resolved.name)
            binding.alias_to_table[key] = resolved.name
        return binding

    def _check_columns(self, expr: exp.Expression, binding: _Binding) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        has_derived = bool(binding.derived_aliases) or expr.find(exp.Subquery) is not None
        # Output aliases may be referenced by name in ORDER BY / HAVING (e.g. ORDER BY late_pct).
        output_aliases = {a.alias.lower() for a in expr.find_all(exp.Alias) if a.alias}
        for col in expr.find_all(exp.Column):
            qualifier = col.table.lower()
            name = col.name
            if qualifier:
                if qualifier in binding.derived_aliases:
                    continue
                table = binding.alias_to_table.get(qualifier)
                if table is None:
                    continue  # unresolved qualifier (already reported or derived)
                if not self._catalog.has_column(table, name):
                    issues.append(
                        ValidationIssue("UNKNOWN_COLUMN", f"Unknown column '{qualifier}.{name}'.")
                    )
                continue
            if has_derived or not binding.base_tables:
                continue  # too complex to resolve safely; EXPLAIN is the backstop
            if name.lower() in output_aliases:
                continue
            owners = [t for t in binding.base_tables if self._catalog.has_column(t, name)]
            if not owners:
                issues.append(ValidationIssue("UNKNOWN_COLUMN", f"Unknown column '{name}'."))
            elif len(owners) > 1:
                issues.append(
                    ValidationIssue(
                        "AMBIGUOUS_COLUMN",
                        f"Column '{name}' is ambiguous across {', '.join(owners)}.",
                    )
                )
        return issues

    def _check_joins(self, expr: exp.Expression, binding: _Binding) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        joins = list(expr.find_all(exp.Join))
        for join in joins:
            on = join.args.get("on")
            using = join.args.get("using")
            if on is None and not using:
                issues.append(
                    ValidationIssue(
                        "CARTESIAN_JOIN",
                        "Join without an ON/USING condition produces a cartesian product.",
                    )
                )
            elif on is not None and not self._join_is_fk_backed(on, binding):
                # Equating the primary keys of two different tables is never a real relationship
                # (e.g. orders.id = customers.id) — block it. Other non-FK joins stay advisory,
                # because legitimate ones exist (e.g. exchange_rates.currency = orders.currency).
                if self._join_equates_primary_keys(on, binding):
                    issues.append(
                        ValidationIssue(
                            "NON_FK_JOIN",
                            "Join equates the primary keys of two unrelated tables, which is not "
                            "a valid relationship.",
                        )
                    )
                else:
                    issues.append(
                        ValidationIssue(
                            "NON_FK_JOIN",
                            "Join is not backed by a known foreign-key relationship.",
                            severity="warning",
                        )
                    )
        if joins and len(joins) >= 2 and expr.find(exp.AggFunc) is not None:
            issues.append(
                ValidationIssue(
                    "FAN_OUT",
                    "Aggregating across multiple one-to-many joins can double-count rows.",
                    severity="warning",
                )
            )
        return issues

    def _join_equates_primary_keys(self, on: exp.Expression, binding: _Binding) -> bool:
        for eq in on.find_all(exp.EQ):
            left, right = eq.this, eq.expression
            if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
                continue
            lt = binding.alias_to_table.get(left.table.lower())
            rt = binding.alias_to_table.get(right.table.lower())
            if lt is None or rt is None or lt.lower() == rt.lower():
                continue
            if self._is_sole_primary_key(lt, left.name) and self._is_sole_primary_key(
                rt, right.name
            ):
                return True
        return False

    def _is_sole_primary_key(self, table: str, column: str) -> bool:
        resolved = self._catalog.get_table(table)
        if resolved is None:
            return False
        return tuple(pk.lower() for pk in resolved.primary_key) == (column.lower(),)

    def _join_is_fk_backed(self, on: exp.Expression, binding: _Binding) -> bool:
        for eq in on.find_all(exp.EQ):
            left, right = eq.this, eq.expression
            if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
                continue
            pair = self._resolve_pair(left, right, binding)
            if pair is None:
                continue
            if pair in self._fk_pairs or _reverse(pair) in self._fk_pairs:
                return True
        return False

    def _resolve_pair(
        self, left: exp.Column, right: exp.Column, binding: _Binding
    ) -> tuple[str, str, str, str] | None:
        lt = binding.alias_to_table.get(left.table.lower())
        rt = binding.alias_to_table.get(right.table.lower())
        if lt is None or rt is None:
            return None
        return (lt.lower(), left.name.lower(), rt.lower(), right.name.lower())


def _function_names(fn: exp.Func) -> set[str]:
    """All lowercased names a function node might be known by: its literal name (for Anonymous)
    and the canonical SQL names of its dedicated sqlglot class."""
    names: set[str] = set()
    literal = (getattr(fn, "name", "") or "").lower()
    if literal:
        names.add(literal)
    sql_names = getattr(type(fn), "sql_names", None)
    if callable(sql_names):
        with suppress(Exception):  # sql_names() can raise on base/abstract nodes
            names |= {str(n).lower() for n in sql_names()}
    return names


def _foreign_key_pairs(catalog: SchemaCatalog) -> set[tuple[str, str, str, str]]:
    pairs: set[tuple[str, str, str, str]] = set()
    for table in catalog.tables:
        for fk in table.foreign_keys:
            pairs.add(
                (table.name.lower(), fk.column.lower(), fk.ref_table.lower(), fk.ref_column.lower())
            )
    return pairs


def _reverse(pair: tuple[str, str, str, str]) -> tuple[str, str, str, str]:
    a, b, c, d = pair
    return (c, d, a, b)


def _clean(message: str) -> str:
    return message.strip().splitlines()[0] if message.strip() else "Query failed to execute."
