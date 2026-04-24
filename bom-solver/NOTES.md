# NOTES — BOM Solver

## Shipped

- v1: 2026-04-24, commit febc25d, branch `claude/setup-bom-solver-project-XqiRv` (pending merge to main)

## Decisions

### Phase 1

| Decision | Choice | Reason |
|----------|--------|--------|
| Build tool | `uv` with `tool.uv.package = false` | `uv` was present; set `package = false` because this is an app, not an installable library — skips the hatchling editable-build step that requires a named package directory |
| src layout | `src/solver.py`, `src/validation.py`, `src/app.py` | PRD names solver, validation, and Streamlit app as distinct concerns; flat `src/` keeps imports simple without a package layer until Phase 2 makes that necessary |
| Test boilerplate | Single placeholder test that passes | Lets us confirm the pytest wiring works before writing real fixtures |
| `tests/fixtures/.gitkeep` | Added | Keeps the empty directory in git |
| Run command | `streamlit run src/app.py` | Matches PRD §6.3 |

### Phase 1 → Phase 2 resolutions (open questions closed)

| Question | Decision | Reason |
|----------|----------|--------|
| `src/` as a package? | Rename `src/` → `bom_solver/`, add `__init__.py`, re-enable hatchling build | Project name `bom-solver` normalises to `bom_solver`; hatchling auto-discovers the directory without extra config. Avoids `sys.path` hacks. Imports become `from bom_solver.solver import …`. Run command becomes `streamlit run bom_solver/app.py`. |
| Session-state persistence | File-based auto-save to `~/.bom-solver/autosave.json` | Simpler than `streamlit-js-eval`; survives tab close; no extra dependency; can swap for true browser storage later if users ask. |

### Phase 2

| Decision | Choice | Reason |
|----------|--------|--------|
| Sign convention | Keep `s_i` notation; add concrete PRD §12 worked example in docstring | A single concrete expansion is more useful than a redundant second abstraction |
| All-locked (m=0) handling | Route through normal infeasibility pipeline (no special-case exit) | PRD §4.4.1 applies regardless of how many rows are currently unlocked; the search still tries subsets of size 1, 2, 3. Unlocking 1 row when m=0 gives 1 unknown and 2 equations — feasible only when that row's Cu% equals `b_copper / b_mass` (the search will usually land on k=2; that's correct) |
| Data structure | `Material` dataclass + `SolveResult` dataclass | Plain dataclasses keep the interface clear without requiring Pydantic |
| Fixture format | JSON files in `tests/fixtures/`; loaded via `json.load`; test parametrised over filenames | Fixtures can be read, edited, and diffed without running Python |
| PRD §12 answer discrepancy | Use corrected values (Product=50, Waste=50) in the fixture; document the error | PRD states Product=60, Waste=40 but 60×0.40 + 40×0.10 = 28 ≠ 25. The solver must be mathematically correct. |

### Phase 2 cont.

| Decision | Choice | Reason |
|----------|--------|--------|
| `cu_pct_locked=False` handling | Raise `ValueError` in `solve()`; also a validation rule in `validation.py` | PRD §3.2 excludes composition solving from v1. Silent ignore causes subtle breaks when v2 ships and old JSON fixtures start behaving differently. Fail loudly now. |
| `test_infeasible_suggestion_matches_fixture` | Removed | Pinned the exact row order of the search, not the contract. The contract is: suggestion is a subset of locked rows, and applying it produces a feasible solution. |

### Phase 2 → Phase 3 fixes

| Decision | Choice | Reason |
|----------|--------|--------|
| `validate_name_unique` case sensitivity | **Case-insensitive** (strip + lower) | Users type "Copper Ore" and "copper ore" and expect a collision. Case-sensitive uniqueness would silently allow duplicates that confuse the solver and the results view. |
| `Material.unit` field | Added with default `"tonne"` | Required by `validate_units_match`. The PRD data model lists Unit as a per-row field even though the UI exposes it as a global selector; keeping it on the dataclass lets validation and future JSON import/export round-trip the value. Existing fixtures gain the field via the default. |
| `ValidationError.row_id=None` convention | Documented in module docstring and inline comment | `None` = whole-BOM error (global banner in UI); `int` = row-specific error (inline highlight). Whoever writes the UI wiring needs this distinction explicit. |

### PRD §12 discrepancy — FLAG: PRD document not yet updated

The PRD §12 worked example states Product=60, Waste=40 given Ore=100 at 25% Cu,
Product at 40% Cu, Waste at 10% Cu.  The copper balance does not hold:
  60 × 40 + 40 × 10 = 2400 + 400 = 2800 ≠ 2500 (= 100 × 25).
The correct answer is Product=50, Waste=50:
  50 × 40 + 50 × 10 = 2000 + 500 = 2500 ✓.

Fixture `01_prd_example.json` uses the corrected values.  The solver is correct.
**TODO (PRD owner):** In the PRD §12 results table, change Product from 60 → 50
and Waste from 40 → 50.  Remove this flag once the PRD is updated.

### Phase 3 UI tweaks (approved changes to initial sketch)

| # | Change | Reason |
|---|--------|--------|
| 1 | Row-level validation errors appear **below the table**, grouped by row ID — not in a sidebar | `st.data_editor` has no inline cell decoration; grouping by row is cleaner than a flat list |
| 2 | State 1 results panel adds **"N rows unchanged"** line after the changes block | Users want to see at a glance that unlocked-but-near-optimal rows were left alone |
| 3 | State 2 unlock suggestion uses **k-aware wording**: "unlock any one of" when suggestion.length == 1, "unlock these N rows" when suggestion.length ≥ 2 | The k=1 case is lighter — users need to unlock only one row, not all listed rows |
| 4 | Autosave restore prompt **includes relative timestamp**: "A session from 2 hours ago was found." | Helps users decide whether to restore or discard stale data |
| 5 | Autosave is **debounced by content hash** — write skipped if hash(df + unit) unchanged | Prevents redundant disk writes on every Streamlit re-run while the user is idle |

## Phase 3 UI Layout Sketch

### Page structure

```
┌─────────────────────────────────────────────────────────────────────┐
│  BOM Mass & Copper Balance Solver                    [unit selector] │
│  ─────────────────────────────────────────────────────────────────  │
│  [Solve ▶]   [Clear Solution]   [Reset All]                         │
├─────────────────────────────────────────────────────────────────────┤
│  [global validation banners — one per whole-BOM error]              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Material table (st.data_editor)                             │  │
│  │  Columns: Row ID | Material | Type | Cu% | Cu%🔒 | Qty | 🔒  │  │
│  │  Row-level validation errors show as ⚠ icon + tooltip text   │  │
│  │  Locked rows: read-only Qty cell, lock icon filled            │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  [+ Add row]                                                        │
├─────────────────────────────────────────────────────────────────────┤
│  RESULTS PANEL  (three states — see below)                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Column layout for the data_editor table

| Column        | Editable?           | Notes                                          |
|---------------|---------------------|------------------------------------------------|
| Row ID        | No (auto)           | Stable identifier shown for error messages     |
| Material      | Yes                 | Name field                                     |
| Type          | Yes (selectbox)     | Input / Output / By-product                    |
| Cu %          | Yes                 | 0–100 float                                    |
| Cu% locked    | Yes (checkbox)      | Always True in v1; shown but greyed            |
| Quantity      | Yes (unless locked) | Float ≥ 0; read-only when Locked=True          |
| Locked        | Yes (checkbox)      | Locks the Quantity field                       |

The `unit` selector lives outside the table as a single `st.selectbox` at top-right; its value is written to all rows on change.

### Validation error rendering

**Row-level errors** (row_id is not None): `st.data_editor` doesn't support inline cell decoration, so errors appear as a compact `st.warning` block below the table listing each offending row by ID and name. Example:
> ⚠ Row 3 (Ore): Material name must not be empty.

**Global errors** (row_id is None): `st.error` banner above the table. Example:
> ✖ At least one row must be marked as Input.

The Solve button is disabled (`disabled=True`) while any validation error exists.

### Results panel — three states

**State 0 — not yet solved** (no solve has been attempted this session):
> *(empty — show nothing so the page stays clean on load)*

**State 1 — solved cleanly** (feasible=True):
```
Mass balance     ✅   residual: 0.000 tonne
Copper balance   ✅   residual: 0.000 tonne

Changes from your entries:
  Product: 60.0 → 50.0   (−10.0)
  Waste:   40.0 → 50.0   (+10.0)
```
Objective label: "Minimised total absolute change from starting values (L1)."

**State 2 — infeasible** (feasible=False):
```
Mass balance     ❌   residual: 20.000 tonne
Copper balance   ❌   residual: 5.000 tonne

Cannot solve with current locks.
Suggestion: unlock any of these rows to proceed:
  → Row 1 (Ore)   → Row 3 (Waste)
```
If suggestion is None (>3 conflicts): "Too many locked conflicts. Review all locked rows."

### Button behaviour

- **Solve**: run `validate_materials()` first; if any errors, show them and do nothing. Otherwise call `solve()`, store the result in `st.session_state`, re-render results panel.
- **Clear Solution**: wipe `session_state.result` and `session_state.solved_quantities`; keep table data and lock state. Results panel returns to State 0.
- **Reset All**: wipe everything (`session_state` cleared); table reverts to one empty row. Also delete `~/.bom-solver/autosave.json`.

### Auto-save / restore flow

On every `st.data_editor` edit: write `~/.bom-solver/autosave.json` containing the full materials list (as JSON).

On app launch: if the file exists, show a `st.info` prompt:
> "A previous session was found. [Restore] [Discard]"
Restore loads the JSON into `session_state`. Discard deletes the file. No silent auto-restore.

## Testing Principles

> Tests should verify contracts, not implementation choices. If the same code change could break a test without breaking the feature, the test is too tight.

## Open Questions

*(none)*
