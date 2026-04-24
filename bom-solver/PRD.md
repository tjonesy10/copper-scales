# Product Requirements Document (PRD)
## Project: Local Python Web App for BOM Mass & Copper Balance Solver

---

## 1. Overview

### 1.1 Purpose
The goal of this product is to provide a **local, browser-based Python application** that lets users create and manage a **Bill of Materials (BOM)** while ensuring:

- **Mass Balance**: Total input quantity equals total output quantity (including by-products)
- **Copper Percentage Balance**: Total copper mass in outputs equals total copper mass in inputs

The app will let users **enter materials by hand**, set constraints, and compute **valid solutions automatically**, even when some values are locked.

---

### 1.2 Target User
- Primary: Supply Chain Analysts, Process Engineers, Metallurgists
- Secondary: Operations planners who work with material flows

---

### 1.3 Key Value Proposition
- Cuts out manual spreadsheet trial-and-error
- Gives **automated feasible solutions**
- Supports **locking with flexible recompute**
- Builds confidence in **mass and composition balance**

---

## 2. Goals & Objectives

### 2.1 Functional Goals
- Let users enter BOM data by hand
- Enforce mass and copper balance
- Support partial locking of variables
- Generate valid solutions automatically

### 2.2 Non-Functional Goals
- Runs locally, no cloud needed
- Light and fast (under 2 seconds solve time for typical data)
- Simple, spreadsheet-like UI

---

## 3. Scope

### 3.1 In Scope
- Data entry interface
- Constraint solver for balancing
- Locking mechanism
- Solution suggestions, including multiple candidate solutions

### 3.2 Out of Scope (v1)
- Multi-element balancing beyond copper
- Cloud sync or multi-user collaboration
- ERP system integration
- Solving for Cu% (composition is always user-entered in v1)
- Negative quantities or reverse flows
- Time-series or batch tracking
- Uncertainty ranges on inputs

---

## 4. Functional Requirements

### 4.1 Data Model

Each row is one material with these fields:

| Field Name       | Type        | Description |
|----------------|------------|-------------|
| Row ID         | Integer    | Stable ID for error messages |
| Material       | String     | Name or identifier |
| Material Type  | Enum       | Input / Output / By-product |
| Copper %       | Float (%)  | Copper content |
| Quantity       | Float      | Material mass |
| Unit           | Enum       | kg, tonne, lb. Must match across all rows |
| Locked         | Boolean    | Whether quantity is fixed |
| Cu % Locked    | Boolean    | Whether composition is fixed (default true) |

**Global settings:**
- Mass unit (applied to all rows)
- Tolerance values (see §4.2.3)

**Note on Material Type:** Input, Output, and By-product labels affect reporting only. The math treats Output and By-product the same way. The split lets users separate intended product from residual streams in the results view. No hidden behavior depends on the label.

---

### 4.2 Core Calculations

#### 4.2.1 Mass Balance Constraint
\[
\sum Inputs = \sum Outputs + \sum Byproducts
\]

#### 4.2.2 Copper Balance Constraint
Total copper mass is conserved. The sum of (quantity times Cu%) across inputs equals the sum across outputs and by-products.

\[
\sum (Input \times Cu\%) = \sum (Output \times Cu\%) + \sum (Byproduct \times Cu\%)
\]

#### 4.2.3 Numerical Tolerance
A balance passes when residuals fall below:

- Mass balance: absolute residual less than 0.001 of total input mass
- Copper balance: absolute residual less than 0.001 of total copper mass

Tolerances are config values. The results panel shows actual residuals, not just pass/fail icons.

---

### 4.3 User Input Features
- Editable spreadsheet-style table
- Manual entry of:
  - Material name
  - Type
  - Copper %
  - Quantity
  - Unit (global setting)
- Lock toggle per row (separate for Quantity and Cu%)

---

### 4.4 Locking Behavior
- Locked quantities stay fixed during solving
- Unlocked quantities get adjusted by the solver
- If the system cannot be solved:
  - Show a clear error
  - Suggest a minimal unlock set (see §4.4.1)

#### 4.4.1 Infeasibility Handling
When no solution exists:

1. Find the smallest set of locked rows whose unlocking would make the system feasible.
2. Cap the search at subsets of size 3. Beyond that, show a generic "too many conflicts" message and highlight the full locked set.
3. Present the suggestion as: "Unlock any of these rows to proceed: [row 3, row 7]."

Use iterative constraint relaxation, not brute-force subset search.

---

### 4.5 Solver Requirements

#### Solver Inputs:
- Known values (locked variables)
- Unknown quantities (unlocked variables)
- Constraints (mass and copper balance)
- User-entered starting values for unlocked rows (if any)

#### Solver Outputs:
- Valid set of quantities that satisfy constraints
- Alternative solutions when the system is underdetermined
- Error when infeasible
- Residual values for each balance equation

#### Solver Behavior:
Must handle:
- Fully determined systems
- Underdetermined systems (return one answer by default, multiple on request)
- Overconstrained systems (return infeasibility with unlock suggestion)

#### Solver Objective (Default):
When the system is underdetermined, the solver picks the answer that **minimizes the sum of absolute changes in quantity** across all unlocked materials.

\[
\min \sum_i |x_i - x_i^{start}|
\]

Where:
- \(x_i\) is the solved quantity for material *i*
- \(x_i^{start}\) is the user-entered starting quantity for material *i*
- Sum runs over unlocked rows only

This objective keeps solutions close to what the user entered. It favors small edits across many rows over one big edit to a single row, which matches how users reason about material flows. It also gives sparse adjustments when that's the best fit, since L1 minimization tends to leave some variables untouched.

If no starting value exists for an unlocked row, treat its start as zero.

**Implementation:** Formulate as a linear program. Introduce auxiliary variables \(d_i \geq |x_i - x_i^{start}|\) and minimize \(\sum d_i\) subject to the balance constraints plus \(x_i \geq 0\). Solve with `scipy.optimize.linprog`.

#### Constraints applied to all solves:
- Balance equations (mass and copper)
- Locked variables fixed at user values
- Non-negativity: \(x_i \geq 0\) for all quantities

---

### 4.6 Solution Modes

| Mode | Behavior |
|------|--------|
| Auto Solve | Adjust unlocked quantities using the default objective |
| Suggest Solutions | Return up to 5 distinct valid solutions, sampled by varying one free variable across its valid range |
| Optimize | Optional future feature (e.g., custom objectives) |

The UI shows which objective is active so users know what "Solve" is optimizing.

---

## 5. User Experience (UX)

### 5.1 Layout

- **Top Section**
  - App title
  - Solve button
  - Clear Solution button
  - Reset All button

- **Main Panel**
  - Editable table with rows for materials
  - Global unit selector

- **Bottom Section**
  - Results validation
    - Mass balance check ✅ / ❌ with residual value
    - Copper balance check ✅ / ❌ with residual value
  - Summary of which rows changed and by how much

**Button behavior:**
- **Clear Solution**: wipes solver-computed values, keeps user input and locks
- **Reset All**: wipes everything, returns to empty table

---

### 5.2 Interaction Flow

1. User enters materials and values
2. User locks desired quantities
3. User clicks Solve
4. App:
   - Validates input
   - Computes balances
   - Updates unlocked fields
   - Shows results, residuals, and change summary

---

### 5.3 Error Handling

| Scenario | Behavior |
|----------|--------|
| No solution exists | Show clear error and suggest unlock set |
| Conflicting locks | Highlight conflicting rows |
| Invalid data | Show inline validation errors |

#### 5.3.1 Input Validation Rules
Check at entry time, before solve:

- Material name: not empty, unique per row
- Copper %: between 0 and 100 inclusive
- Quantity: not negative when entered
- At least one row marked Input, at least one marked Output
- Units must match across all rows

Show errors inline. Disable the Solve button until all errors clear.

---

### 5.4 Persistence

Even in v1, the app supports:

- **Auto-save** current table to browser local storage on every edit
- **Export to JSON** button for manual save
- **Import from JSON** for reload

Without this, users lose work on tab close. It's cheap to build and heads off the top user complaint.

---

## 6. Technical Design

### 6.1 Architecture

- **Frontend: Streamlit** (chosen for v1)

Rationale:
- Reactive model fits the edit-solve-display loop
- `st.data_editor` covers v1 grid needs
- Single-file Python keeps local deploy trivial
- Flask plus a JS grid is the right call only if users need Excel-grade editing, which is a v2 signal

Revisit this choice if user testing shows grid limits block core tasks.

- **Backend**
  - Python solver
  - Linear algebra and optimization engine

---

### 6.2 Solver Approach

#### Libraries:
- `numpy` for linear algebra
- `scipy.optimize.linprog` for the L1 minimization objective

#### Problem Formulation:
Solve the system:
Ax = b

Where:
- x = quantities
- A = constraint matrix (mass and copper rows)
- b = totals

Add:
- Locked variables fixed at user values
- Non-negativity: x ≥ 0
- Objective: minimize sum of absolute changes from starting values

---

### 6.3 Local Deployment

- Run with:
  - `streamlit run bom_solver/app.py`
- No database needed (in-memory plus file-based autosave to `~/.bom-solver/autosave.json`)

---

## 7. Performance Requirements

- Max rows: around 100 materials
- Solve time: under 2 seconds
- Memory: under 200MB

---

## 8. Future Enhancements

- Excel import and export
- Save and load named scenarios
- Scenario comparison view (show what changed between two solves)
- Multi-element balancing
- Solving for Cu%
- Custom objectives (e.g., minimize waste, maximize recovery)

---

## 9. Success Metrics

- User can create and solve a BOM in under 5 minutes
- Full enforcement of constraints within tolerance
- Zero manual recalculation needed

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Underdetermined system confusion | Default objective plus clear messaging plus multiple-solution mode |
| Overconstrained systems | Detect early, suggest minimal unlock set |
| Solver instability | Use `scipy.optimize.linprog` with input validation and bounds |
| Floating-point residuals | Report residuals with a tolerance threshold, don't require exact zero |
| Lost work on tab close | Auto-save to local storage plus JSON export |

---

## 11. Acceptance Criteria

- ✅ Five test users complete the §12 example in under 3 minutes without help
- ✅ Solver returns correct answers on a fixture set of 20 known cases
- ✅ Mass and copper residuals fall below tolerance on all passing cases
- ✅ Infeasible fixtures return the correct minimal unlock set on 90% of cases
- ✅ Solve completes in under 2 seconds for 100-row inputs
- ✅ User can lock any quantity
- ✅ UI blocks Solve when input is invalid and shows inline errors
- ✅ Auto-save restores the last table on page reload

---

## 12. Example Use Case

### Input:

| Material | Type | Cu % | Qty | Locked |
|---------|------|------|-----|--------|
| Ore     | Input | 25% | 100 | ✅ |
| Product | Output | 40% | ? | ❌ |
| Waste   | By-product | 10% | ? | ❌ |

### Output:
- Product Qty: 50
- Waste Qty: 50
- Constraints satisfied:
  - Total mass: 100 in, 100 out ✓
  - Total copper: 25 in (100 × 25%), 25 out (50 × 40% + 50 × 10%) ✓
  - Mass residual: 0.000
  - Copper residual: 0.000

---

## 13. Summary

This app replaces spreadsheet trial-and-error with a **structured, constraint-driven solver** that gives users:
- Accuracy
- Flexibility
- Speed

It aims to feel **as simple as Excel** while solving constrained material balance problems that Excel handles poorly.
