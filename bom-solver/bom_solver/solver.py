"""
BOM Mass & Copper Balance Solver — LP Formulation
==================================================

NOTATION
--------
n       Total number of materials in the BOM.
U       Index set of *unlocked* materials  (|U| = m).
L       Index set of *locked* materials    (|L| = n - m).
s_i     Sign of material i:  +1 for Input, -1 for Output / By-product.
c_i     Copper fraction of material i  (= Cu_pct_i / 100).
x_i     Quantity of material i.
          • i ∈ L : fixed at the user-supplied value x_i^locked.
          • i ∈ U : decision variable, x_i ≥ 0.
x_i^0   User-supplied *starting* quantity for unlocked material i
          (treated as 0 if not provided).

WORKED EXAMPLE (PRD §12 — ore / product / waste)
-------------------------------------------------
Material  Type        s_i   c_i    x_i
Ore       Input       +1    0.25   100  (locked)
Product   Output      −1    0.40   ?    (unlocked)
Waste     By-product  −1    0.10   ?    (unlocked)

L = {Ore},  U = {Product, Waste},  m = 2

b_mass   = −(+1 · 100) = −100
b_copper = −(+1 · 0.25 · 100) = −25

A_eq = [[ −1,  −1  ],    ← s_i row
        [ −0.40, −0.10]]  ← s_i·c_i row

Solving A_eq · [x_P, x_W]ᵀ = [−100, −25]ᵀ gives x_P = 50, x_W = 50.
(Note: the PRD §12 answer of 60/40 is incorrect; 60·0.40 + 40·0.10 = 28 ≠ 25.)

BALANCE CONSTRAINTS
-------------------
Mass balance (total inputs equal total outputs + by-products):

    Σ_{i ∈ U}  s_i · x_i  =  b_mass
    b_mass  =  −Σ_{j ∈ L}  s_j · x_j^locked

Copper balance (copper mass is conserved):

    Σ_{i ∈ U}  s_i · c_i · x_i  =  b_copper
    b_copper  =  −Σ_{j ∈ L}  s_j · c_j · x_j^locked

In matrix form:  A_eq · x_U = b,   A_eq ∈ ℝ^{2 × m},   b ∈ ℝ^2.

Row 0 of A_eq:  [s_i            for i ∈ U]   (mass balance coefficients)
Row 1 of A_eq:  [s_i · c_i      for i ∈ U]   (copper balance coefficients)

Note: if all materials have c_i = 0 the two rows are proportional and the
system has only one independent constraint.  The LP objective still resolves
the underdetermined case uniquely via the L1 term.

NON-NEGATIVITY
--------------
    x_i ≥ 0   for all i ∈ U.

OBJECTIVE — L1 MINIMISATION
-----------------------------
Minimise the total absolute change from starting quantities:

    min  Σ_{i ∈ U}  |x_i − x_i^0|

This is non-linear.  Linearise by introducing auxiliary variables d_i ≥ 0
satisfying  d_i ≥ |x_i − x_i^0|,  which is equivalent to:

    d_i ≥  x_i − x_i^0   →   x_i − d_i ≤  x_i^0          (1)
    d_i ≥ −x_i + x_i^0   →  −x_i − d_i ≤ −x_i^0          (2)

The minimiser drives each d_i to exactly |x_i − x_i^0| at optimality.

LP VECTOR LAYOUT  (scipy.optimize.linprog convention)
------------------------------------------------------
Decision vector  z ∈ ℝ^{2m}:

    z = [ x_0, x_1, …, x_{m-1},   d_0, d_1, …, d_{m-1} ]
          |--- x-block (m) ---|    |--- d-block (m) ---|

Objective vector  c ∈ ℝ^{2m}:

    c = [ 0, …, 0,   1, …, 1 ]
        (m zeros)  (m ones)

Equality constraints  A_eq_full · z = b   (shape 2 × 2m):

    A_eq_full = [ A_eq | 0_{2×m} ]

    (d variables do not appear in the balance equations)

Inequality constraints  A_ub · z ≤ b_ub   (shape 2m × 2m):

    For each k = 0 … m−1  (k indexes the k-th unlocked material):

        Row 2k   corresponds to constraint (1):
            A_ub[2k, k]   =  1    A_ub[2k, m+k]  = −1    b_ub[2k]   =  x_k^0
        Row 2k+1 corresponds to constraint (2):
            A_ub[2k+1, k] = −1    A_ub[2k+1, m+k] = −1   b_ub[2k+1] = −x_k^0

    All other entries in each row are 0.

Bounds:
    x_k ∈ [0, ∞)   for k = 0 … m−1
    d_k ∈ [0, ∞)   for k = m … 2m−1

EDGE CASES
----------
m = 0 (all variables locked):
    No LP needed.  Compute residuals directly.  If both are within tolerance,
    the BOM is already balanced; otherwise return an infeasibility error.

Rank-deficient A_eq (e.g. all c_i = 0 → rows are proportional):
    The LP is still well-posed; the L1 objective selects the unique minimum-
    change solution among infinitely many feasible points.

linprog status codes used:
    0 → Optimal solution found  (feasible)
    2 → Infeasible               (trigger unlock-suggestion logic in caller)
    3 → Unbounded                (should not occur given x ≥ 0 and d ≥ 0;
                                  treated as an unexpected solver error)

RESIDUALS
---------
After solving, residuals are computed over *all* materials (locked + unlocked):

    r_mass   = Σ_all  s_i · x_i           (should be 0 at optimum)
    r_copper = Σ_all  s_i · c_i · x_i     (should be 0 at optimum)

These raw values are returned alongside the solved quantities so the UI can
display them directly.  The caller applies the tolerance thresholds defined
in PRD §4.2.3.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

_INPUT = "Input"
_OUTPUT = "Output"
_BYPRODUCT = "By-product"


@dataclass
class Material:
    row_id: int
    name: str
    material_type: str          # "Input" | "Output" | "By-product"
    cu_pct: float               # 0–100
    quantity: float             # ≥ 0
    locked: bool
    unit: str = "tonne"         # "kg" | "tonne" | "lb" — must match across all rows
    cu_pct_locked: bool = True
    start_quantity: float | None = None


@dataclass
class SolveResult:
    feasible: bool
    quantities: dict[int, float]        # row_id → solved quantity
    mass_residual: float
    copper_residual: float
    unlock_suggestion: list[int] | None = None  # row_ids; None when feasible
    message: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sign(material_type: str) -> int:
    return 1 if material_type == _INPUT else -1


def _compute_residuals(
    materials: list[Material],
    quantities: dict[int, float],
) -> tuple[float, float]:
    r_mass = r_copper = 0.0
    for mat in materials:
        q = quantities[mat.row_id]
        s = _sign(mat.material_type)
        r_mass += s * q
        r_copper += s * (mat.cu_pct / 100.0) * q
    return r_mass, r_copper


def _run_lp(
    materials: list[Material],
    unlocked_ids: set[int],
) -> dict[int, float] | None:
    """Solve the LP for the given unlocked set. Returns quantities or None if infeasible."""
    unlocked = [m for m in materials if m.row_id in unlocked_ids]
    locked   = [m for m in materials if m.row_id not in unlocked_ids]
    n_u = len(unlocked)

    # RHS: locked contributions moved to the right-hand side
    b_mass   = -sum(_sign(m.material_type) * m.quantity for m in locked)
    b_copper = -sum(_sign(m.material_type) * (m.cu_pct / 100.0) * m.quantity for m in locked)
    b = np.array([b_mass, b_copper])

    # A_eq (2 × n_u): balance matrix for unlocked variables
    A_eq = np.zeros((2, n_u))
    for k, mat in enumerate(unlocked):
        s = _sign(mat.material_type)
        A_eq[0, k] = s
        A_eq[1, k] = s * mat.cu_pct / 100.0

    # Starting values x^0 (default 0 per PRD §4.5)
    x0 = np.array(
        [m.start_quantity if m.start_quantity is not None else 0.0 for m in unlocked]
    )

    # Decision vector z = [x_0…x_{n_u-1}, d_0…d_{n_u-1}]
    c_obj = np.concatenate([np.zeros(n_u), np.ones(n_u)])

    # Equality constraints: [A_eq | 0] z = b  (d variables absent)
    A_eq_full = np.hstack([A_eq, np.zeros((2, n_u))])

    # Inequality constraints: 2 rows per unlocked variable
    #   Row 2k:   x_k - d_k ≤  x_k^0   (d_k ≥ x_k - x_k^0)
    #   Row 2k+1: -x_k - d_k ≤ -x_k^0  (d_k ≥ x_k^0 - x_k)
    A_ub = np.zeros((2 * n_u, 2 * n_u))
    b_ub = np.zeros(2 * n_u)
    for k in range(n_u):
        A_ub[2 * k,     k]       =  1.0
        A_ub[2 * k,     n_u + k] = -1.0
        b_ub[2 * k]              =  x0[k]
        A_ub[2 * k + 1, k]       = -1.0
        A_ub[2 * k + 1, n_u + k] = -1.0
        b_ub[2 * k + 1]          = -x0[k]

    bounds = [(0.0, None)] * (2 * n_u)

    res = linprog(
        c_obj,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq_full,
        b_eq=b,
        bounds=bounds,
        method="highs",
    )

    if res.status != 0:
        return None

    x_solved = res.x[:n_u]
    quantities = {m.row_id: m.quantity for m in locked}
    for k, mat in enumerate(unlocked):
        quantities[mat.row_id] = float(x_solved[k])
    return quantities


def _find_unlock_suggestion(
    materials: list[Material],
    current_unlocked_ids: set[int],
    tol_mass: float,
    tol_copper: float,
) -> list[int] | None:
    """Return the smallest subset (size 1–3) of locked rows whose unlocking yields feasibility.

    When current_unlocked_ids is empty (all locked), a single-row unlock gives
    1 unknown and 2 equations — feasible only when the unlocked row's Cu% equals
    b_copper/b_mass.  The search typically lands on k=2 in that case; that's
    correct, not a bug.
    """
    locked_ids = [m.row_id for m in materials if m.row_id not in current_unlocked_ids]

    for k in range(1, 4):
        for subset in itertools.combinations(locked_ids, k):
            candidate_ids = current_unlocked_ids | set(subset)
            result = _run_lp(materials, candidate_ids)
            if result is None:
                continue
            r_mass, r_copper = _compute_residuals(materials, result)
            if abs(r_mass) <= tol_mass and abs(r_copper) <= tol_copper:
                return list(subset)

    return None  # no subset of size ≤ 3 resolves the conflict


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def solve(
    materials: list[Material],
    mass_tol_frac: float = 1e-3,
    copper_tol_frac: float = 1e-3,
) -> SolveResult:
    """Solve the BOM for balanced quantities. Returns a SolveResult with feasible=True
    on success or feasible=False with an unlock suggestion on failure."""
    if any(not m.cu_pct_locked for m in materials):
        raise ValueError(
            "Cu% composition solving is not supported in v1. "
            "All materials must have cu_pct_locked=True. "
            f"Offending row_ids: {[m.row_id for m in materials if not m.cu_pct_locked]}"
        )

    total_input_mass   = sum(m.quantity for m in materials if m.material_type == _INPUT)
    total_copper_mass  = sum(
        m.quantity * m.cu_pct / 100.0 for m in materials if m.material_type == _INPUT
    )
    tol_mass   = mass_tol_frac   * max(total_input_mass,  1e-10)
    tol_copper = copper_tol_frac * max(total_copper_mass, 1e-10)

    unlocked_ids = {m.row_id for m in materials if not m.locked}

    if not unlocked_ids:
        # m = 0: check whether locked values already balance
        base_qtys = {m.row_id: m.quantity for m in materials}
        r_mass, r_copper = _compute_residuals(materials, base_qtys)
        if abs(r_mass) <= tol_mass and abs(r_copper) <= tol_copper:
            return SolveResult(
                feasible=True,
                quantities=base_qtys,
                mass_residual=r_mass,
                copper_residual=r_copper,
            )
        # Imbalanced all-locked: fall through to unlock search
        infeasible_qtys = base_qtys
        infeasible_r_mass, infeasible_r_copper = r_mass, r_copper

    else:
        result_qtys = _run_lp(materials, unlocked_ids)
        if result_qtys is not None:
            r_mass, r_copper = _compute_residuals(materials, result_qtys)
            return SolveResult(
                feasible=True,
                quantities=result_qtys,
                mass_residual=r_mass,
                copper_residual=r_copper,
            )
        infeasible_qtys = {m.row_id: m.quantity for m in materials}
        infeasible_r_mass, infeasible_r_copper = _compute_residuals(
            materials, infeasible_qtys
        )

    suggestion = _find_unlock_suggestion(materials, unlocked_ids, tol_mass, tol_copper)

    if suggestion is None:
        msg = (
            "System is over-constrained. Too many conflicts to resolve automatically. "
            "Review all locked rows."
        )
    else:
        ids_str = ", ".join(f"row {rid}" for rid in suggestion)
        msg = f"Unlock any of these rows to proceed: {ids_str}."

    return SolveResult(
        feasible=False,
        quantities=infeasible_qtys,
        mass_residual=infeasible_r_mass,
        copper_residual=infeasible_r_copper,
        unlock_suggestion=suggestion,
        message=msg,
    )
