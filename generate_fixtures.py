"""Temporary script: generate the 16 additional test fixtures for Phase 2."""
import json
from pathlib import Path

OUT = Path("tests/fixtures")


def row(row_id, name, mat_type, cu_pct, qty, locked=True, cu_pct_locked=True, start=None):
    return {
        "row_id": row_id, "name": name, "material_type": mat_type,
        "cu_pct": float(cu_pct), "quantity": float(qty),
        "locked": locked, "cu_pct_locked": cu_pct_locked,
        "start_quantity": float(start) if start is not None else None,
    }


def inp(row_id, cu_pct, qty, name=None, locked=True):
    return row(row_id, name or f"Input {row_id}", "Input", cu_pct, qty, locked=locked)


def out(row_id, cu_pct, qty, name=None, locked=True, start=None):
    return row(row_id, name or f"Output {row_id}", "Output", cu_pct, qty,
               locked=locked, start=start)


def byp(row_id, cu_pct, qty, name=None, locked=True):
    return row(row_id, name or f"By-product {row_id}", "By-product", cu_pct, qty, locked=locked)


def save(name, description, materials, expected):
    data = {"description": description, "materials": materials, "expected": expected}
    path = OUT / name
    path.write_text(json.dumps(data, indent=2))
    print(f"  wrote {path}")


# ---------------------------------------------------------------------------
# Fixture 05 — determined, 3 rows, 0 % and 100 % Cu edge cases
# Input 25 % × 100 → Output (100 %) 25 + Output (0 %) 75
# ---------------------------------------------------------------------------
save("05_det_extremes.json",
     "Determined 3-row: single locked input feeds one 100%-Cu and one 0%-Cu unlocked "
     "output. Both edge-case compositions covered in one fixture.",
     [
         inp(1, 25.0, 100.0, "Ore"),
         out(2, 100.0, 0.0, "Pure Copper", locked=False),
         out(3, 0.0,   0.0, "Gangue",      locked=False),
     ],
     {"feasible": True,
      "quantities": {"1": 100.0, "2": 25.0, "3": 75.0}})


# ---------------------------------------------------------------------------
# Fixture 06 — determined, 5 rows, 100 % Cu input, zero-Cu by-product
# ---------------------------------------------------------------------------
# b_mass = -(8+92-20) = -80;  b_copper = -(8 + 9.2) = -17.2
# O1 50%: x1=34.4, O2 0%: x2=45.6
save("06_det_5row.json",
     "Determined 5-row: 100%-Cu input and zero-Cu locked by-product; two unlocked "
     "outputs (50% and 0% Cu). Tests 100% boundary in locked row.",
     [
         inp(1, 100.0, 8.0,  "Blister copper"),
         inp(2,  10.0, 92.0, "Low-grade feed"),
         byp(3,   0.0, 20.0, "Barren slag"),
         out(4,  50.0,  0.0, "Product",   locked=False),
         out(5,   0.0,  0.0, "Discard",   locked=False),
     ],
     {"feasible": True,
      "quantities": {"1": 8.0, "2": 92.0, "3": 20.0, "4": 34.4, "5": 45.6}})


# ---------------------------------------------------------------------------
# Fixture 07 — determined, 10 rows
# 5 locked inputs, 2 locked by-products, 1 locked output, 2 unlocked outputs
# b_mass=-230, b_copper=-45 → O(0%)=140, O(50%)=90
# ---------------------------------------------------------------------------
save("07_det_10row.json",
     "Determined 10-row: five locked inputs, two locked by-products, one locked "
     "output; two unlocked outputs (0% and 50% Cu).",
     [
         inp(1, 10.0, 100.0),
         inp(2, 25.0,  80.0),
         inp(3, 35.0,  60.0),
         inp(4, 45.0,  40.0),
         inp(5, 55.0,  30.0),
         byp(6,  5.0,  15.0),
         byp(7, 15.0,  25.0),
         out(8, 90.0,  40.0),            # locked output
         out(9,  0.0,   0.0, locked=False),
         out(10, 50.0,  0.0, locked=False),
     ],
     {"feasible": True,
      "quantities": {
          "1": 100.0, "2": 80.0, "3": 60.0, "4": 40.0, "5": 30.0,
          "6": 15.0,  "7": 25.0, "8": 40.0, "9": 140.0, "10": 90.0}})


# ---------------------------------------------------------------------------
# Fixture 08 — determined, 25 rows
# Inputs 1-17: Cu 5%…85% (step 5%), Qty=10 each  → mass=170, Cu=76.5
# By-products 18-20: Cu=5%, Qty=8                 → mass=-24, Cu=-1.2
# Locked outputs 21-23: Cu=40%, Qty=6             → mass=-18, Cu=-7.2
# b_mass=-128, b_copper=-68.1
# O(0%)=14.5, O(60%)=113.5
# ---------------------------------------------------------------------------
mats_08 = []
for k in range(1, 18):          # rows 1-17
    mats_08.append(inp(k, 5.0 * k, 10.0, f"Input {k}%Cu"))
for i, rid in enumerate(range(18, 21)):  # rows 18-20
    mats_08.append(byp(rid, 5.0, 8.0, f"By-product {i+1}"))
for i, rid in enumerate(range(21, 24)):  # rows 21-23
    mats_08.append(out(rid, 40.0, 6.0, f"Locked output {i+1}"))
mats_08.append(out(24, 0.0,  0.0, "Zero-Cu product",   locked=False))
mats_08.append(out(25, 60.0, 0.0, "High-Cu product",   locked=False))

save("08_det_25row.json",
     "Determined 25-row: 17 inputs (5–85% Cu), 3 locked by-products, 3 locked "
     "outputs, 2 unlocked outputs (0% and 60% Cu).",
     mats_08,
     {"feasible": True,
      "quantities": {"24": 14.5, "25": 113.5}})


# ---------------------------------------------------------------------------
# Fixture 09 — determined, 50 rows
# 40 locked inputs: Cu=20%, Qty=10  → mass=400, Cu=80
# 4 locked by-products: Cu=5%, Qty=10  → mass=-40, Cu=-2
# 4 locked outputs: Cu=30%, Qty=10  → mass=-40, Cu=-12
# b_mass=-320, b_copper=-66
# O(0%)=56, O(25%)=264
# ---------------------------------------------------------------------------
mats_09 = []
for k in range(1, 41):
    mats_09.append(inp(k, 20.0, 10.0, f"Feed {k}"))
for k in range(41, 45):
    mats_09.append(byp(k, 5.0, 10.0, f"Slag {k}"))
for k in range(45, 49):
    mats_09.append(out(k, 30.0, 10.0, f"Intermediate {k}"))
mats_09.append(out(49, 0.0,  0.0, "Zero-Cu tail",   locked=False))
mats_09.append(out(50, 25.0, 0.0, "Copper product", locked=False))

save("09_det_50row.json",
     "Determined 50-row: 40 identical inputs, 4 locked by-products, 4 locked "
     "outputs, 2 unlocked outputs (0% and 25% Cu). Performance and scale check.",
     mats_09,
     {"feasible": True,
      "quantities": {"49": 56.0, "50": 264.0}})


# ---------------------------------------------------------------------------
# Fixture 10 — determined, 100 rows
# 88 locked inputs: Cu=20%, Qty=10  → mass=880, Cu=176
# 4 locked by-products: Cu=5%, Qty=10  → mass=-40, Cu=-2
# 6 locked outputs: Cu=30%, Qty=10  → mass=-60, Cu=-18
# b_mass=-780, b_copper=-156
# O(0%)=156, O(25%)=624
# ---------------------------------------------------------------------------
mats_10 = []
for k in range(1, 89):
    mats_10.append(inp(k, 20.0, 10.0, f"Feed {k}"))
for k in range(89, 93):
    mats_10.append(byp(k, 5.0, 10.0, f"Slag {k}"))
for k in range(93, 99):
    mats_10.append(out(k, 30.0, 10.0, f"Intermediate {k}"))
mats_10.append(out(99,  0.0,  0.0, "Zero-Cu tail",   locked=False))
mats_10.append(out(100, 25.0, 0.0, "Copper product", locked=False))

save("10_det_100row.json",
     "Determined 100-row: 88 identical inputs, 4 locked by-products, 6 locked "
     "outputs, 2 unlocked outputs. PRD §11 acceptance criterion (100-row scale).",
     mats_10,
     {"feasible": True,
      "quantities": {"99": 156.0, "100": 624.0}})


# ---------------------------------------------------------------------------
# Fixture 11 — underdetermined, unique L1 optimum
# Input 25%×100; 3 unlocked outputs (50%, 10%, 30%) with starts (40,30,30).
# Parameterize on x_C=t: x_A=37.5-0.5t, x_B=62.5-0.5t.
# L1(t): minimum at t=30 → (22.5, 47.5, 30).
# ---------------------------------------------------------------------------
save("11_und_l1_choice.json",
     "Underdetermined, 3 unlocked outputs with distinct Cu%: unique L1 minimum. "
     "Starts (40,30,30) not feasible; solver picks (22.5,47.5,30) minimising total change.",
     [
         inp(1, 25.0, 100.0, "Feed", locked=True),
         out(2, 50.0,  40.0, "High-Cu product", locked=False, start=40.0),
         out(3, 10.0,  30.0, "Low-Cu product",  locked=False, start=30.0),
         out(4, 30.0,  30.0, "Mid-Cu product",  locked=False, start=30.0),
     ],
     {"feasible": True,
      "quantities": {"1": 100.0, "2": 22.5, "3": 47.5, "4": 30.0}})


# ---------------------------------------------------------------------------
# Fixture 12 — underdetermined, unique L1 minimum at equal split
# Input 30%×120; 3 unlocked outputs (60%,20%,10%) starts (50,40,30).
# t parameterises: x_A=30+0.25t, x_B=90-1.25t, x_C=t; minimum at t=40 → (40,40,40).
# ---------------------------------------------------------------------------
save("12_und_equal_split.json",
     "Underdetermined, 3 unlocked outputs: L1 minimum falls at the equal split (40,40,40). "
     "Starts (50,40,30) are not feasible; solver converges to the symmetric minimum.",
     [
         inp(1, 30.0, 120.0, "Feed"),
         out(2, 60.0,  50.0, "High-Cu product", locked=False, start=50.0),
         out(3, 20.0,  40.0, "Mid-Cu product",  locked=False, start=40.0),
         out(4, 10.0,  30.0, "Low-Cu product",  locked=False, start=30.0),
     ],
     {"feasible": True,
      "quantities": {"1": 120.0, "2": 40.0, "3": 40.0, "4": 40.0}})


# ---------------------------------------------------------------------------
# Fixture 13 — underdetermined, starting values already at a feasible point
# Rank-1 system (both outputs same Cu%). Starts satisfy constraint → L1=0 → returned unchanged.
# ---------------------------------------------------------------------------
save("13_und_feasible_start.json",
     "Underdetermined, starts already feasible: one input (30%) feeds two outputs "
     "of the same Cu% (30%). Rank-1 constraint; L1 returns starting values unchanged.",
     [
         inp(1, 30.0, 100.0, "Feed"),
         out(2, 30.0,  60.0, "Product A", locked=False, start=60.0),
         out(3, 30.0,  40.0, "Product B", locked=False, start=40.0),
     ],
     {"feasible": True,
      "quantities": {"1": 100.0, "2": 60.0, "3": 40.0}})


# ---------------------------------------------------------------------------
# Fixture 14 — underdetermined, zero starting values
# 50%-Cu input × 100; 3 unlocked outputs (50%) with start=null.
# Only mass constraint; starts=0; multiple optima — verify feasibility only.
# ---------------------------------------------------------------------------
save("14_und_zero_starts.json",
     "Underdetermined, all starts=null (default 0): 3 unlocked outputs share the "
     "same Cu% as the input. Only one independent constraint; multiple L1 optima. "
     "Fixture verifies feasibility and residuals only, not exact quantities.",
     [
         inp(1, 50.0, 100.0, "Feed"),
         out(2, 50.0,   0.0, "Stream A", locked=False),
         out(3, 50.0,   0.0, "Stream B", locked=False),
         out(4, 50.0,   0.0, "Stream C", locked=False),
     ],
     {"feasible": True})   # no "quantities" key → residuals-only check


# ---------------------------------------------------------------------------
# Fixture 15 — underdetermined, 4 free variables, 2 independent constraints
# 2 locked inputs (40%×100, 60%×100); 4 unlocked outputs (100%,50%,20%,0%).
# Multiple L1 optima in 2-D parameter space → residuals-only check.
# ---------------------------------------------------------------------------
save("15_und_four_free.json",
     "Underdetermined with 4 unlocked outputs and 2 locked inputs (total mass 200, "
     "copper 100). Two independent constraints, two degrees of freedom. "
     "Verifies feasibility and residuals only.",
     [
         inp(1, 40.0, 100.0, "Feed A"),
         inp(2, 60.0, 100.0, "Feed B"),
         out(3, 100.0, 0.0, "Pure Cu product", locked=False, start=50.0),
         out(4,  50.0, 0.0, "Blister copper",  locked=False, start=60.0),
         out(5,  20.0, 0.0, "Concentrate",     locked=False, start=40.0),
         out(6,   0.0, 0.0, "Tailings",        locked=False, start=50.0),
     ],
     {"feasible": True})


# ---------------------------------------------------------------------------
# Fixture 16 — underdetermined, many rows (15 rows)
# 10 locked inputs + 1 locked by-product; 4 unlocked outputs, all same Cu%.
# Only mass constraint; multiple L1 optima → residuals-only check.
# ---------------------------------------------------------------------------
mats_16 = [inp(k, 30.0, 10.0, f"Feed {k}") for k in range(1, 11)]
mats_16.append(byp(11, 30.0, 10.0, "Locked slag"))
for k in range(12, 16):
    mats_16.append(out(k, 30.0, 20.0, f"Stream {k}", locked=False, start=20.0))

save("16_und_many_rows.json",
     "Underdetermined, 15 rows: 10 locked inputs and 1 locked by-product feed 4 "
     "unlocked outputs sharing the same Cu% (rank-1 constraint). "
     "Verifies feasibility and residuals only.",
     mats_16,
     {"feasible": True})


# ---------------------------------------------------------------------------
# Fixture 17 — infeasible, mass-only imbalance
# All Cu%=0 → copper trivially balanced; mass imbalance (100 in, 80 out).
# k=1 unlock sufficient.
# ---------------------------------------------------------------------------
save("17_inf_mass_only.json",
     "Infeasible: all Cu%=0, copper trivially balanced, mass imbalanced (100 in, "
     "80 out). Any single-row unlock restores balance.",
     [
         inp(1, 0.0, 60.0, "Zero-Cu input A"),
         inp(2, 0.0, 40.0, "Zero-Cu input B"),
         out(3, 0.0, 80.0, "Zero-Cu output"),
     ],
     {"feasible": False})


# ---------------------------------------------------------------------------
# Fixture 18 — infeasible, copper-only imbalance (mass balanced)
# Input Cu%=30%×100, Output Cu%=20%×100 → mass residual=0, copper≠0.
# k=1 unlock: each row gives inconsistent 1-equation-2-constraints system.
# k=2: unlock both → trivial (0,0) solution satisfies constraints.
# ---------------------------------------------------------------------------
save("18_inf_copper_only.json",
     "Infeasible: mass exactly balanced (100 in, 100 out) but copper not (30≠20). "
     "k=1 unlock always gives inconsistent 1-var/2-eq system; k=2 (unlock both) "
     "resolves via trivial (0,0) solution.",
     [
         inp(1, 30.0, 100.0, "Feed"),
         out(2, 20.0, 100.0, "Product"),
     ],
     {"feasible": False})


# ---------------------------------------------------------------------------
# Fixture 19 — infeasible, both mass and copper imbalanced; needs k=2
# Input 50%×100; Output A 30%×70; Output B 50%×20. All locked.
# k=1: every single-row unlock gives inconsistent system.
# k=2 {rows 1,2}: solves to (20,0) for the two unlocked rows.
# ---------------------------------------------------------------------------
save("19_inf_both_k2.json",
     "Infeasible, both mass and copper imbalanced; no single-row unlock resolves it. "
     "k=2 (unlock rows 1 and 2) gives (20,0), satisfying all constraints.",
     [
         inp(1, 50.0, 100.0, "Feed"),
         out(2, 30.0,  70.0, "Product A"),
         out(3, 50.0,  20.0, "Product B"),
     ],
     {"feasible": False})


# ---------------------------------------------------------------------------
# Fixture 20 — cu_pct_locked=False triggers validation rule
# ---------------------------------------------------------------------------
save("20_inf_cu_pct_unlocked.json",
     "One row has cu_pct_locked=False, which is unsupported in v1 (PRD §3.2). "
     "validate_materials() must return a cu_pct_locked_v1 error for row 2. "
     "solve() must raise ValueError.",
     [
         inp(1, 30.0, 100.0, "Feed"),
         row(2, "Product", "Output", 30.0, 100.0,
             locked=False, cu_pct_locked=False, start=None),
     ],
     {"feasible": False,
      "validation_errors": [{"rule": "cu_pct_locked_v1", "row_id": 2}]})


print("Done.")
