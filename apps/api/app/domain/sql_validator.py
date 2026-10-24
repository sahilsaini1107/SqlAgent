"""Deterministic SQL validation gate.

Runs after every generation/repair/optimization. No LLM is involved. The order is cheapest
and most decisive first: parse -> single statement -> read-only -> functions -> schema binding
-> joins -> (optional) real-engine EXPLAIN. Errors block the query; warnings are advisory.

This is one half of "the LLM proposes, code decides" — the other half is the read-only
database layer, which independently enforces safety even if a
bug here let something through.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.domain.query_policy import ALLOWED_FUNCTIONS
from app.domain.schema_catalog import SchemaCatalog
from app.domain.validation import ValidationIssue, ValidationResult

_FORBIDDEN_NAMES = [
    "Insert", "Update", "Delete", "Merge", "Drop", "Create", "Alter",
    "TruncateTable", "Command", "Pragma", "Attach", "Detach",
    "Transaction", "Commit", "Rollback", "Set", "Use",
]
_FORBIDDEN_TYPES = tuple(getattr(exp, name) for name in _FORBIDDEN_NAMES if hasattr(exp, name))

_ALLOWED_ROOT_NAMES = ["Select", "Union", "Intersect", "Except", "Subquery"]
_ALLOWED_ROOTS = tuple(getattr(exp, name) for name in _ALLOWED_ROOT_NAMES if hasattr(exp, name))


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
        execute_check: Callable[[str], None] | None = None,
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
            if self._execute_check is not None:
                try:
                    self._execute_check(final_sql)
                except Exception as err:  # engine is the final arbiter of syntax/columns
                    issues.append(ValidationIssue("EXECUTION_ERROR", _clean(str(err))))
                    return ValidationResult(issues)
            return ValidationResult(issues, final_sql=final_sql)
        return result

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
        for fn in expr.find_all(exp.Anonymous):
            name = (fn.name or "").lower()
            if name and name not in self._allowed_functions:
                issues.append(
                    ValidationIssue("UNSUPPORTED_FUNCTION", f"Function '{name}' is not allowed.")
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
