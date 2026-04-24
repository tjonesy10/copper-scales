"""
Input validation for BOM rows and global settings (PRD §5.3.1 and §4.1).

Each rule is a pure function:  rule(materials) -> list[ValidationError]

Call validate_materials() to run all rules at once.  The UI can also call
individual rules to highlight specific error classes inline.

ValidationError.row_id convention:
  - int  → error on a specific row; the UI renders this inline next to that row.
  - None → error on the whole BOM (no single row to blame); the UI renders
           this as a global banner above the table.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from solver import Material

_OUTPUT_TYPES = ("Output", "By-product")


@dataclass
class ValidationError:
    rule: str           # machine-readable rule name for UI routing
    message: str        # human-readable description
    row_id: int | None = None
    # row_id=None → applies to the whole BOM, not a specific row.
    # The UI renders these differently: global banner vs. inline row error.


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

def validate_name_not_empty(materials: list[Material]) -> list[ValidationError]:
    """Material name must not be empty or blank."""
    return [
        ValidationError(
            rule="name_not_empty",
            message="Material name must not be empty.",
            row_id=m.row_id,
        )
        for m in materials
        if not m.name.strip()
    ]


def validate_name_unique(materials: list[Material]) -> list[ValidationError]:
    """Material names must be unique (case-insensitive, whitespace-stripped).

    'Copper Ore' and 'copper ore' collide — users expect this to be caught.
    """
    seen: dict[str, int] = {}
    errors: list[ValidationError] = []
    for m in materials:
        key = m.name.strip().lower()
        if key in seen:
            errors.append(ValidationError(
                rule="name_unique",
                message=f"Duplicate material name '{m.name}' (first seen on row {seen[key]}).",
                row_id=m.row_id,
            ))
        else:
            seen[key] = m.row_id
    return errors


def validate_cu_pct_range(materials: list[Material]) -> list[ValidationError]:
    """Cu% must be between 0 and 100 inclusive."""
    return [
        ValidationError(
            rule="cu_pct_range",
            message=f"Cu% must be between 0 and 100, got {m.cu_pct}.",
            row_id=m.row_id,
        )
        for m in materials
        if not (0.0 <= m.cu_pct <= 100.0)
    ]


def validate_quantity_non_negative(materials: list[Material]) -> list[ValidationError]:
    """Entered quantities must not be negative."""
    return [
        ValidationError(
            rule="quantity_non_negative",
            message=f"Quantity must not be negative, got {m.quantity}.",
            row_id=m.row_id,
        )
        for m in materials
        if m.quantity < 0.0
    ]


def validate_has_input(materials: list[Material]) -> list[ValidationError]:
    """At least one row must be marked as Input."""
    if not any(m.material_type == "Input" for m in materials):
        return [ValidationError(
            rule="has_input",
            message="At least one row must be marked as Input.",
            row_id=None,
        )]
    return []


def validate_has_output(materials: list[Material]) -> list[ValidationError]:
    """At least one row must be marked as Output or By-product."""
    if not any(m.material_type in _OUTPUT_TYPES for m in materials):
        return [ValidationError(
            rule="has_output",
            message="At least one row must be marked as Output or By-product.",
            row_id=None,
        )]
    return []


def validate_cu_pct_locked(materials: list[Material]) -> list[ValidationError]:
    """Cu% composition solving is not supported in v1; cu_pct_locked must be True."""
    return [
        ValidationError(
            rule="cu_pct_locked_v1",
            message=(
                "Cu% composition solving is not supported in v1. "
                "Set cu_pct_locked=True for this row."
            ),
            row_id=m.row_id,
        )
        for m in materials
        if not m.cu_pct_locked
    ]


def validate_units_match(materials: list[Material]) -> list[ValidationError]:
    """All rows must use the same mass unit (PRD §4.1).

    Returns one global error (row_id=None) listing which rows carry which unit
    so the user can see exactly where the mismatch is.
    """
    if not materials:
        return []
    by_unit: dict[str, list[int]] = defaultdict(list)
    for m in materials:
        by_unit[m.unit].append(m.row_id)
    if len(by_unit) == 1:
        return []
    parts = "; ".join(
        f"{unit} on rows {ids}" for unit, ids in sorted(by_unit.items())
    )
    return [ValidationError(
        rule="units_match",
        message=f"All rows must use the same unit. Found: {parts}.",
        row_id=None,
    )]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

_RULES = [
    validate_name_not_empty,
    validate_name_unique,
    validate_cu_pct_range,
    validate_quantity_non_negative,
    validate_has_input,
    validate_has_output,
    validate_cu_pct_locked,
    validate_units_match,
]


def validate_materials(materials: list[Material]) -> list[ValidationError]:
    """Run all validation rules. Returns an empty list when the input is valid."""
    errors: list[ValidationError] = []
    for rule in _RULES:
        errors.extend(rule(materials))
    return errors
