"""Read-only query policy: resource limits and the SQL function allowlist.

The function allowlist is deny-by-default. Only side-effect-free scalar/aggregate functions
are permitted; anything unknown (including dangerous SQLite functions like ``load_extension``,
``readfile``, ``writefile``) is rejected by both the validator and the execution authorizer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryLimits:
    max_rows: int = 1000
    timeout_ms: int = 5000


ALLOWED_FUNCTIONS: frozenset[str] = frozenset(
    {
        # aggregates
        "count", "sum", "avg", "min", "max", "total", "group_concat",
        # window (ranking, offsets, running values)
        "row_number", "rank", "dense_rank", "percent_rank", "cume_dist", "ntile",
        "lag", "lead", "first_value", "last_value", "nth_value",
        # string
        "length", "lower", "upper", "trim", "ltrim", "rtrim", "substr", "substring",
        "replace", "instr", "printf", "format", "char", "unicode", "hex", "quote",
        "concat", "concat_ws", "like", "glob",
        # numeric
        "abs", "round", "ceil", "ceiling", "floor", "sign", "mod", "power", "sqrt",
        # date / time
        "date", "time", "datetime", "julianday", "strftime", "unixepoch", "timediff",
        # conditional / null
        "coalesce", "nullif", "ifnull", "iif", "nvl", "greatest", "least",
        # type / misc (safe)
        "cast", "typeof", "likelihood", "likely", "unlikely",
    }
)
