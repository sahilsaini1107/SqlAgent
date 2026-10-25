"""Validation result types shared by the validator, graph, and API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

IssueCode = Literal[
    "PARSE_ERROR",
    "MULTI_STATEMENT",
    "FORBIDDEN_OPERATION",
    "UNSUPPORTED_FUNCTION",
    "FORBIDDEN_FUNCTION",
    "UNKNOWN_TABLE",
    "UNKNOWN_COLUMN",
    "AMBIGUOUS_COLUMN",
    "CARTESIAN_JOIN",
    "NON_FK_JOIN",
    "FAN_OUT",
    "EXECUTION_ERROR",
]

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class ValidationIssue:
    code: IssueCode
    message: str
    severity: Severity = "error"

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "severity": self.severity}


@dataclass(frozen=True)
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)
    final_sql: str | None = None

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def passed(self) -> bool:
        return not self.errors
