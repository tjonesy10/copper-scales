"""Tests for bom_solver.validation — one test per rule, plus an integration test."""

import json
from pathlib import Path

import pytest

from bom_solver.solver import Material
from bom_solver.validation import (
    ValidationError,
    validate_cu_pct_locked,
    validate_cu_pct_range,
    validate_has_input,
    validate_has_output,
    validate_materials,
    validate_name_not_empty,
    validate_name_unique,
    validate_quantity_non_negative,
    validate_units_match,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def mat(row_id=1, name="Feed", mat_type="Input", cu_pct=30.0, qty=100.0,
        locked=True, cu_pct_locked=True, unit="tonne"):
    return Material(
        row_id=row_id, name=name, material_type=mat_type,
        cu_pct=cu_pct, quantity=qty,
        locked=locked, cu_pct_locked=cu_pct_locked, unit=unit,
    )


def valid_pair():
    """Minimal valid BOM: one input, one output."""
    return [
        mat(1, "Feed",    "Input",  30.0, 100.0),
        mat(2, "Product", "Output", 30.0, 100.0),
    ]


# ---------------------------------------------------------------------------
# validate_name_not_empty
# ---------------------------------------------------------------------------

def test_name_not_empty_passes():
    assert validate_name_not_empty(valid_pair()) == []


def test_name_not_empty_catches_blank():
    mats = [mat(1, "  "), mat(2, "Product", "Output")]
    errors = validate_name_not_empty(mats)
    assert len(errors) == 1
    assert errors[0].rule == "name_not_empty"
    assert errors[0].row_id == 1


def test_name_not_empty_catches_empty_string():
    mats = [mat(1, ""), mat(2, "Product", "Output")]
    errors = validate_name_not_empty(mats)
    assert len(errors) == 1
    assert errors[0].row_id == 1


# ---------------------------------------------------------------------------
# validate_name_unique — case-insensitive, whitespace-stripped
# ---------------------------------------------------------------------------

def test_name_unique_passes():
    assert validate_name_unique(valid_pair()) == []


def test_name_unique_catches_duplicate():
    mats = [mat(1, "Feed"), mat(2, "Feed", "Output")]
    errors = validate_name_unique(mats)
    assert len(errors) == 1
    assert errors[0].rule == "name_unique"
    assert errors[0].row_id == 2   # second occurrence is the error


def test_name_unique_strips_whitespace():
    mats = [mat(1, "Feed "), mat(2, " Feed", "Output")]
    errors = validate_name_unique(mats)
    assert len(errors) == 1


def test_name_unique_is_case_insensitive():
    """'Copper Ore' and 'copper ore' must collide."""
    mats = [mat(1, "Copper Ore"), mat(2, "copper ore", "Output")]
    errors = validate_name_unique(mats)
    assert len(errors) == 1
    assert errors[0].row_id == 2


def test_name_unique_different_names_pass():
    mats = [mat(1, "Feed A"), mat(2, "Feed B", "Output")]
    assert validate_name_unique(mats) == []


# ---------------------------------------------------------------------------
# validate_cu_pct_range
# ---------------------------------------------------------------------------

def test_cu_pct_range_passes_boundaries():
    mats = [mat(1, cu_pct=0.0), mat(2, "Product", "Output", cu_pct=100.0)]
    assert validate_cu_pct_range(mats) == []


def test_cu_pct_range_catches_negative():
    mats = [mat(1, cu_pct=-1.0), mat(2, "Product", "Output")]
    errors = validate_cu_pct_range(mats)
    assert len(errors) == 1
    assert errors[0].rule == "cu_pct_range"
    assert errors[0].row_id == 1


def test_cu_pct_range_catches_over_100():
    mats = [mat(1), mat(2, "Product", "Output", cu_pct=100.1)]
    errors = validate_cu_pct_range(mats)
    assert len(errors) == 1
    assert errors[0].row_id == 2


# ---------------------------------------------------------------------------
# validate_quantity_non_negative
# ---------------------------------------------------------------------------

def test_quantity_non_negative_passes_zero():
    mats = [mat(1, qty=0.0), mat(2, "Product", "Output", qty=0.0)]
    assert validate_quantity_non_negative(mats) == []


def test_quantity_non_negative_catches_negative():
    mats = [mat(1, qty=-5.0), mat(2, "Product", "Output")]
    errors = validate_quantity_non_negative(mats)
    assert len(errors) == 1
    assert errors[0].rule == "quantity_non_negative"
    assert errors[0].row_id == 1


# ---------------------------------------------------------------------------
# validate_has_input
# ---------------------------------------------------------------------------

def test_has_input_passes():
    assert validate_has_input(valid_pair()) == []


def test_has_input_catches_missing():
    mats = [mat(1, "A", "Output"), mat(2, "B", "By-product")]
    errors = validate_has_input(mats)
    assert len(errors) == 1
    assert errors[0].rule == "has_input"
    assert errors[0].row_id is None    # global error


# ---------------------------------------------------------------------------
# validate_has_output
# ---------------------------------------------------------------------------

def test_has_output_passes_with_output():
    assert validate_has_output(valid_pair()) == []


def test_has_output_passes_with_byproduct():
    mats = [mat(1), mat(2, "Slag", "By-product")]
    assert validate_has_output(mats) == []


def test_has_output_catches_missing():
    mats = [mat(1), mat(2, "Also input", "Input")]
    errors = validate_has_output(mats)
    assert len(errors) == 1
    assert errors[0].rule == "has_output"
    assert errors[0].row_id is None


# ---------------------------------------------------------------------------
# validate_cu_pct_locked
# ---------------------------------------------------------------------------

def test_cu_pct_locked_passes():
    assert validate_cu_pct_locked(valid_pair()) == []


def test_cu_pct_locked_catches_false():
    mats = [mat(1), mat(2, "Product", "Output", cu_pct_locked=False)]
    errors = validate_cu_pct_locked(mats)
    assert len(errors) == 1
    assert errors[0].rule == "cu_pct_locked_v1"
    assert errors[0].row_id == 2


def test_cu_pct_locked_from_fixture():
    """validate_materials detects cu_pct_locked=False from the JSON fixture."""
    with open(FIXTURES_DIR / "20_inf_cu_pct_unlocked.json") as f:
        data = json.load(f)
    materials = [
        Material(
            row_id=m["row_id"], name=m["name"], material_type=m["material_type"],
            cu_pct=m["cu_pct"], quantity=m["quantity"],
            locked=m["locked"], cu_pct_locked=m.get("cu_pct_locked", True),
            unit=m.get("unit", "tonne"),
        )
        for m in data["materials"]
    ]
    errors = validate_materials(materials)
    cu_errors = [e for e in errors if e.rule == "cu_pct_locked_v1"]
    expected = data["expected"]["validation_errors"]
    assert len(cu_errors) == len(expected)
    for err, exp in zip(cu_errors, expected):
        assert err.row_id == exp["row_id"]


# ---------------------------------------------------------------------------
# validate_units_match
# ---------------------------------------------------------------------------

def test_units_match_passes_all_same():
    mats = [mat(1, unit="tonne"), mat(2, "Product", "Output", unit="tonne")]
    assert validate_units_match(mats) == []


def test_units_match_catches_mixed():
    mats = [
        mat(1, unit="tonne"),
        mat(2, "Product", "Output", unit="kg"),
    ]
    errors = validate_units_match(mats)
    assert len(errors) == 1
    assert errors[0].rule == "units_match"
    assert errors[0].row_id is None         # global error
    assert "kg" in errors[0].message
    assert "tonne" in errors[0].message


def test_units_match_lists_conflicting_rows():
    mats = [
        mat(1, unit="tonne"),
        mat(2, "B", "Input",  unit="kg"),
        mat(3, "C", "Output", unit="tonne"),
        mat(4, "D", "Output", unit="lb"),
    ]
    errors = validate_units_match(mats)
    assert len(errors) == 1
    msg = errors[0].message
    # All three unit names and some row IDs must appear in the message
    assert "kg" in msg
    assert "lb" in msg
    assert "tonne" in msg


def test_units_match_empty_list():
    assert validate_units_match([]) == []


# ---------------------------------------------------------------------------
# Integration test — many errors at once
# ---------------------------------------------------------------------------

def test_validate_materials_multiple_errors():
    """A messy BOM triggers errors from several rules simultaneously."""
    mats = [
        # no name, negative qty, cu_pct too high, mixed unit
        mat(1, "",      "Input",  cu_pct=120.0, qty=-10.0, unit="kg"),
        # duplicate name (case-insensitive), valid otherwise
        mat(2, "X",     "Output", cu_pct=30.0,  qty=50.0,  unit="tonne"),
        mat(3, "x",     "Output", cu_pct=30.0,  qty=50.0,  unit="tonne"),
        # cu_pct_locked=False
        mat(4, "Y",     "Output", cu_pct=30.0,  qty=0.0,   cu_pct_locked=False),
    ]
    errors = validate_materials(mats)
    rules  = {e.rule for e in errors}

    assert "name_not_empty"        in rules   # row 1 (empty string)
    assert "cu_pct_range"          in rules   # row 1 (120%)
    assert "quantity_non_negative" in rules   # row 1 (-10)
    assert "name_unique"           in rules   # row 3 ("x" collides with "X")
    assert "cu_pct_locked_v1"      in rules   # row 4
    assert "units_match"           in rules   # row 1 uses "kg", others "tonne"

    # Every row-level error must carry the right row_id
    row_errors = [e for e in errors if e.row_id is not None]
    assert all(e.row_id in {1, 3, 4} for e in row_errors)


def test_validate_materials_clean_bom():
    assert validate_materials(valid_pair()) == []
