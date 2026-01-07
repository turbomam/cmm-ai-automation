"""Base classes for the validation framework.

This module provides the core data structures and abstract base class
for field validators that verify data integrity in sheets.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Severity levels for validation issues."""

    ERROR = "error"  # Data is definitely wrong
    WARNING = "warning"  # Data is suspicious or incomplete
    INFO = "info"  # Informational finding


class IssueType(str, Enum):
    """Types of validation issues."""

    # ID validation
    INVALID_ID = "invalid_id"  # ID doesn't exist in authoritative source
    BOGUS_XREF = "bogus_xref"  # Cross-reference ID is unrelated to the entity

    # Name/ID consistency
    NAME_MISMATCH = "name_mismatch"  # Name doesn't match ID in authoritative source
    DESIGNATION_MISMATCH = "designation_mismatch"  # Strain designation doesn't match

    # Missing data
    MISSING_VALUE = "missing_value"  # Required field is empty
    MISSING_STRAIN_TAXON = "missing_strain_taxon"  # No strain-level taxon ID

    # Format issues
    INVALID_FORMAT = "invalid_format"  # Value doesn't match expected format
    PARSE_ERROR = "parse_error"  # Could not parse the value

    # Cross-field consistency
    FIELD_CONFLICT = "field_conflict"  # Two fields in same row conflict


@dataclass
class ValidationIssue:
    """A single validation issue found in a sheet.

    Attributes:
        sheet: Name of the sheet file (e.g., "strains.tsv")
        row: Row number in the sheet (1-indexed, header is row 1)
        field: Column name where the issue was found
        issue_type: Category of the issue
        severity: How serious the issue is
        value: The problematic value (if applicable)
        expected: What we expected to find (if applicable)
        actual: What we found from authoritative source (if applicable)
        message: Human-readable description of the issue
        suggestion: Suggested fix (if applicable)
        context: Additional context (other field values, lookup results)
    """

    sheet: str
    row: int
    field: str
    issue_type: IssueType
    severity: Severity
    message: str
    value: str | None = None
    expected: str | None = None
    actual: str | None = None
    suggestion: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Format issue for display."""
        loc = f"{self.sheet}:{self.row}"
        sev = self.severity.value.upper()
        return f"[{sev}] {loc} [{self.issue_type.value}] {self.field}: {self.message}"


@dataclass
class ValidationReport:
    """Aggregated validation results for one or more sheets.

    Attributes:
        sheets_checked: List of sheet names that were validated
        rows_checked: Total number of data rows checked
        issues: List of all validation issues found
        stats: Counts by issue type
        lookup_cache: Cached lookup results for performance
    """

    sheets_checked: list[str] = field(default_factory=list)
    rows_checked: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    lookup_cache: dict[str, Any] = field(default_factory=dict)

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add an issue and update stats."""
        self.issues.append(issue)
        key = issue.issue_type.value
        self.stats[key] = self.stats.get(key, 0) + 1

    def merge(self, other: ValidationReport) -> None:
        """Merge another report into this one."""
        self.sheets_checked.extend(other.sheets_checked)
        self.rows_checked += other.rows_checked
        for issue in other.issues:
            self.add_issue(issue)
        self.lookup_cache.update(other.lookup_cache)

    @property
    def error_count(self) -> int:
        """Count of ERROR severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of WARNING severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        """Count of INFO severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.INFO)

    def get_issues_by_severity(self, severity: Severity) -> list[ValidationIssue]:
        """Get all issues of a specific severity."""
        return [i for i in self.issues if i.severity == severity]

    def get_issues_by_type(self, issue_type: IssueType) -> list[ValidationIssue]:
        """Get all issues of a specific type."""
        return [i for i in self.issues if i.issue_type == issue_type]

    def get_issues_for_row(self, sheet: str, row: int) -> list[ValidationIssue]:
        """Get all issues for a specific row."""
        return [i for i in self.issues if i.sheet == sheet and i.row == row]


class FieldValidator(ABC):
    """Abstract base class for field validators.

    Validators check individual field values against authoritative sources
    and return a list of any issues found.

    Subclasses must implement:
        - validate(): Check a value and return issues
        - name: Property returning the validator's name
    """

    @abstractmethod
    def validate(
        self,
        value: str,
        context: dict[str, Any],
        sheet: str,
        row: int,
        field: str,
    ) -> list[ValidationIssue]:
        """Validate a single field value.

        Args:
            value: The field value to validate
            context: Dict containing other field values from the same row
            sheet: Name of the sheet being validated
            row: Row number (1-indexed)
            field: Column name

        Returns:
            List of ValidationIssue objects (empty if valid)
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return validator name for reporting."""


class ListValidator(FieldValidator):
    """Base class for validators that handle semicolon-separated lists.

    Subclasses should implement validate_item() instead of validate().
    """

    def __init__(self, separator: str = ";"):
        """Initialize with list separator.

        Args:
            separator: Character(s) used to separate list items
        """
        self.separator = separator

    def parse_list(self, value: str) -> list[str]:
        """Parse a separated list into individual items."""
        if not value:
            return []
        return [item.strip() for item in value.split(self.separator) if item.strip()]

    def validate(
        self,
        value: str,
        context: dict[str, Any],
        sheet: str,
        row: int,
        field: str,
    ) -> list[ValidationIssue]:
        """Validate each item in the list."""
        issues: list[ValidationIssue] = []
        items = self.parse_list(value)

        for item in items:
            item_issues = self.validate_item(item, context, sheet, row, field)
            issues.extend(item_issues)

        return issues

    @abstractmethod
    def validate_item(
        self,
        item: str,
        context: dict[str, Any],
        sheet: str,
        row: int,
        field: str,
    ) -> list[ValidationIssue]:
        """Validate a single item from the list.

        Args:
            item: Single item from the list
            context: Dict containing other field values from the same row
            sheet: Name of the sheet being validated
            row: Row number (1-indexed)
            field: Column name

        Returns:
            List of ValidationIssue objects (empty if valid)
        """
