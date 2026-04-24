"""Fixture-driven tests for bom_solver.solver."""

import json
from pathlib import Path

import pytest

from solver import Material, _compute_residuals, _run_lp, solve

FIXTURES_DIR = Path(__file__).parent / "fixtures"

QTY_TOL      = 1e-4   # tolerance for pinned quantity comparisons
RESIDUAL_TOL = 1e-4   # tolerance for verifying unlock suggestions balance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(filename: str) -> dict:
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)


def _materials(data: dict) -> list[Material]:
    return [
        Material(
            row_id=m["row_id"],
            name=m["name"],
            material_type=m["material_type"],
            cu_pct=m["cu_pct"],
            quantity=m["quantity"],
            locked=m["locked"],
            unit=m.get("unit", "tonne"),
            cu_pct_locked=m.get("cu_pct_locked", True),
            start_quantity=m.get("start_quantity"),
        )
        for m in data["materials"]
    ]


def _verify_suggestion(materials: list[Material], suggestion: list[int]) -> None:
    """Assert that unlocking the suggested rows produces a balanced solution."""
    current_unlocked = {m.row_id for m in materials if not m.locked}
    candidate_ids = current_unlocked | set(suggestion)
    result_qtys = _run_lp(materials, candidate_ids)
    assert result_qtys is not None, "LP infeasible even after applying suggestion"
    r_mass, r_copper = _compute_residuals(materials, result_qtys)
    assert abs(r_mass)   <= RESIDUAL_TOL, f"Mass residual {r_mass} after unlock"
    assert abs(r_copper) <= RESIDUAL_TOL, f"Copper residual {r_copper} after unlock"


# ---------------------------------------------------------------------------
# Fixtures that exercise the solver (skip 20 — it's a validation test)
# ---------------------------------------------------------------------------

SOLVER_FIXTURES = [
    "01_prd_example.json",
    "02_fully_determined.json",
    "03_underdetermined.json",
    "04_infeasible.json",
    "05_det_extremes.json",
    "06_det_5row.json",
    "07_det_10row.json",
    "08_det_25row.json",
    "09_det_50row.json",
    "10_det_100row.json",
    "11_und_l1_choice.json",
    "12_und_equal_split.json",
    "13_und_feasible_start.json",
    "14_und_zero_starts.json",
    "15_und_four_free.json",
    "16_und_many_rows.json",
    "17_inf_mass_only.json",
    "18_inf_copper_only.json",
    "19_inf_both_k2.json",
]


@pytest.mark.parametrize("filename", SOLVER_FIXTURES)
def test_fixture(filename):
    """Single parametrised test that checks every contract the fixture declares."""
    data      = _load(filename)
    materials = _materials(data)
    expected  = data["expected"]

    result = solve(materials)

    assert result.feasible == expected["feasible"], (
        f"{filename}: expected feasible={expected['feasible']}, got {result.feasible}"
    )

    if expected["feasible"]:
        assert abs(result.mass_residual)   <= RESIDUAL_TOL, \
            f"{filename}: mass_residual={result.mass_residual}"
        assert abs(result.copper_residual) <= RESIDUAL_TOL, \
            f"{filename}: copper_residual={result.copper_residual}"

        if "quantities" in expected:
            for row_id_str, qty in expected["quantities"].items():
                solved = result.quantities[int(row_id_str)]
                assert abs(solved - qty) <= QTY_TOL, (
                    f"{filename} row {row_id_str}: expected {qty}, got {solved}"
                )
    else:
        assert result.unlock_suggestion is not None, \
            f"{filename}: expected a non-null unlock suggestion"
        locked_ids = {m.row_id for m in materials if m.locked}
        assert set(result.unlock_suggestion).issubset(locked_ids), \
            f"{filename}: suggestion {result.unlock_suggestion} not a subset of locked rows"
        _verify_suggestion(materials, result.unlock_suggestion)


# ---------------------------------------------------------------------------
# cu_pct_locked=False guard in solve()
# ---------------------------------------------------------------------------

def test_solve_raises_on_cu_pct_unlocked():
    """solve() must raise ValueError when any material has cu_pct_locked=False."""
    data      = _load("20_inf_cu_pct_unlocked.json")
    materials = _materials(data)
    with pytest.raises(ValueError, match="cu_pct_locked"):
        solve(materials)


# ---------------------------------------------------------------------------
# Infeasibility contract: suggestion is valid (row IDs + actual balance)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", [
    f for f in SOLVER_FIXTURES
    if "inf" in f
])
def test_infeasible_suggestion_valid(filename):
    """For every infeasible fixture the suggestion must produce a balanced solution."""
    data      = _load(filename)
    materials = _materials(data)
    result    = solve(materials)

    assert not result.feasible
    assert result.unlock_suggestion is not None

    locked_ids = {m.row_id for m in materials if m.locked}
    assert set(result.unlock_suggestion).issubset(locked_ids)
    _verify_suggestion(materials, result.unlock_suggestion)
