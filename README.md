# BOM Mass & Copper Balance Solver

A local, browser-based tool for metallurgists and process engineers who need to balance Bills of Materials by mass and copper content. Enter your materials, lock the quantities you know, and click **Solve** — the app finds the closest valid solution automatically.

No spreadsheet iteration. No cloud. Runs on your laptop.

---

## What it does

Given a Bill of Materials with some quantities locked and others unknown, the solver finds values for the unknowns that satisfy two constraints simultaneously:

- **Mass balance** — total input mass equals total output + by-product mass
- **Copper balance** — copper mass is conserved across inputs and outputs

When multiple solutions exist, it picks the one closest to your starting values (minimum L1 change), so the result stays near what you already know about the process.

### Example

Ore assays at 25% Cu. You know you're feeding 100 t. You want to know how much product (40% Cu) and waste (10% Cu) you'll get:

| Material | Type       | Cu %  | Quantity | Locked |
|----------|------------|-------|----------|--------|
| Ore      | Input      | 25%   | 100 t    | ✅     |
| Product  | Output     | 40%   | ?        | ❌     |
| Waste    | By-product | 10%   | ?        | ❌     |

**Solved:**

| Material | Quantity | Change |
|----------|----------|--------|
| Ore      | 100.000  | —      |
| Product  | 50.000   | —      |
| Waste    | 50.000   | —      |

Mass residual: 0.000 t · Copper residual: 0.000 t

Verification: 50 × 0.40 + 50 × 0.10 = 20 + 5 = 25 = 100 × 0.25 ✓

---

## Quick start

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/tjonesy10/copper-scales.git
cd copper-scales/bom-solver
uv sync
uv run streamlit run bom_solver/app.py
```

Open `http://localhost:8501`. The PRD §12 example is pre-loaded so you can hit **Solve** immediately.

---

## Features

**Locking** — lock any quantity to hold it fixed. The solver adjusts only unlocked rows.

**Infeasibility suggestions** — when no solution exists, the app identifies the smallest set of rows to unlock (up to 3) and tells you exactly which ones. No manual diagnosis.

**L1 objective** — among all feasible solutions, the solver picks the one that minimises total absolute change from your starting values. Solutions stay close to what you entered; the solver makes the smallest correction that balances the books.

**Autosave** — every edit is written to `~/.bom-solver/autosave.json`. Close the tab, reopen the app, restore your session. No work lost.

**Validation** — the Solve button stays disabled until all inputs are valid. Errors appear inline below the table grouped by row.

**Units** — supports tonnes, kg, and lb via a global selector. Mixed units are caught as a validation error.

---

## Running tests

```bash
uv run pytest
```

51 tests across solver and validation. Fixtures cover:
- Fully determined systems (1–100 rows)
- Underdetermined systems (rank-1, multiple free variables, L1 tiebreaking)
- Infeasible systems (mass-only, copper-only, both — k=1 and k=2 unlock cases)
- Validation rules (all 8, individually and combined)

---

## Project layout

```
bom-solver/
├── bom_solver/
│   ├── solver.py       # LP formulation and solve() API
│   ├── validation.py   # 8 validation rules + pipeline
│   └── app.py          # Streamlit UI
├── tests/
│   ├── fixtures/       # 20 JSON test cases
│   ├── test_solver.py
│   └── test_validation.py
├── PRD.md              # Product requirements
└── NOTES.md            # Decision log
```

The solver is independent of Streamlit. `solver.py` and `validation.py` can be imported and tested without a running app.

---

## How the solver works

The problem is formulated as a linear program:

- **Decision variables**: quantities for unlocked rows (x ≥ 0)
- **Equality constraints**: mass balance and copper balance
- **Objective**: minimise Σ |xᵢ − xᵢ⁰| (L1, linearised with auxiliary variables)
- **Solver**: `scipy.optimize.linprog` with the HiGHS backend

When the LP is infeasible, the solver searches subsets of locked rows (size 1, 2, 3) to find the smallest unlock set that restores feasibility. The full formulation is documented in `solver.py`.

---

## Tolerance

Balances are checked against:
- Mass: residual < 0.1% of total input mass
- Copper: residual < 0.1% of total input copper mass

Actual residuals are shown in the results panel regardless of pass/fail.
