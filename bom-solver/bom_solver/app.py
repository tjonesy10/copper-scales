"""Streamlit front-end for the BOM Mass & Copper Balance Solver."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from bom_solver.solver import Material, SolveResult, solve
from bom_solver.validation import validate_materials

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUTOSAVE_PATH = Path.home() / ".bom-solver" / "autosave.json"
UNITS = ["tonne", "kg", "lb"]
MATERIAL_TYPES = ["Input", "Output", "By-product"]

_DEFAULT_ROWS = [
    {"row_id": 1, "name": "Ore",     "material_type": "Input",      "cu_pct": 25.0, "quantity": 100.0, "locked": True,  "cu_pct_locked": True},
    {"row_id": 2, "name": "Product", "material_type": "Output",     "cu_pct": 40.0, "quantity":   0.0, "locked": False, "cu_pct_locked": True},
    {"row_id": 3, "name": "Waste",   "material_type": "By-product", "cu_pct": 10.0, "quantity":   0.0, "locked": False, "cu_pct_locked": True},
]

# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

def _make_default_df() -> pd.DataFrame:
    return pd.DataFrame(_DEFAULT_ROWS)


def _normalise_df(df: pd.DataFrame) -> pd.DataFrame:
    """Fill defaults for any missing columns; reassign row_ids sequentially."""
    df = df.copy()
    if "row_id" not in df.columns or df["row_id"].isna().any():
        df["row_id"] = range(1, len(df) + 1)
    else:
        df["row_id"] = range(1, len(df) + 1)  # always re-sequence after add/delete
    for col, default in [
        ("name", ""),
        ("material_type", "Input"),
        ("cu_pct", 0.0),
        ("quantity", 0.0),
        ("locked", False),
        ("cu_pct_locked", True),
    ]:
        if col not in df.columns:
            df[col] = default
    df["row_id"] = df["row_id"].astype(int)
    df["cu_pct_locked"] = True  # always True in v1 — not editable
    return df.reset_index(drop=True)


def _df_to_materials(df: pd.DataFrame, unit: str) -> list[Material]:
    return [
        Material(
            row_id=int(row["row_id"]),
            name=str(row["name"]),
            material_type=str(row["material_type"]),
            cu_pct=float(row["cu_pct"]),
            quantity=float(row["quantity"]),
            locked=bool(row["locked"]),
            cu_pct_locked=bool(row["cu_pct_locked"]),
            unit=unit,
        )
        for _, row in df.iterrows()
    ]


def _df_hash(df: pd.DataFrame, unit: str) -> str:
    payload = df.to_json(orient="records") + unit
    return hashlib.md5(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Autosave / restore
# ---------------------------------------------------------------------------

def _save_autosave(df: pd.DataFrame, unit: str) -> None:
    AUTOSAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "unit": unit,
        "materials": df.to_dict(orient="records"),
    }
    AUTOSAVE_PATH.write_text(json.dumps(data, indent=2))


def _load_autosave() -> dict | None:
    if not AUTOSAVE_PATH.exists():
        return None
    try:
        return json.loads(AUTOSAVE_PATH.read_text())
    except Exception:
        return None


def _format_age(saved_at_str: str) -> str:
    try:
        saved_at = datetime.fromisoformat(saved_at_str)
        delta = datetime.now(timezone.utc) - saved_at
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            m = seconds // 60
            return f"{m} minute{'s' if m != 1 else ''} ago"
        if seconds < 86400:
            h = seconds // 3600
            return f"{h} hour{'s' if h != 1 else ''} ago"
        d = seconds // 86400
        return f"{d} day{'s' if d != 1 else ''} ago"
    except Exception:
        return "some time ago"


def _delete_autosave() -> None:
    if AUTOSAVE_PATH.exists():
        AUTOSAVE_PATH.unlink()


# ---------------------------------------------------------------------------
# Results panel
# ---------------------------------------------------------------------------

def _render_results(
    result: SolveResult,
    pre_solve_materials: list[Material],
    unit: str,
) -> None:
    st.divider()
    st.subheader("Results")

    if result.feasible:
        col1, col2 = st.columns(2)
        col1.metric("Mass balance", "✅", f"residual: {result.mass_residual:.3f} {unit}")
        col2.metric("Copper balance", "✅", f"residual: {result.copper_residual:.3f} {unit}")

        # Build change summary
        pre_qty = {m.row_id: m.quantity for m in pre_solve_materials}
        changes = []
        unchanged = 0
        for mat in pre_solve_materials:
            if mat.locked:
                continue
            before = pre_qty[mat.row_id]
            after  = result.quantities[mat.row_id]
            diff   = after - before
            if abs(diff) < 1e-6:
                unchanged += 1
            else:
                sign = "+" if diff >= 0 else "−"
                changes.append(
                    f"  **{mat.name}**: {before:.3f} → {after:.3f}   ({sign}{abs(diff):.3f})"
                )

        if changes:
            st.markdown("**Changes from your entries:**")
            for line in changes:
                st.markdown(line)
        if unchanged > 0:
            st.markdown(f"*{unchanged} row{'s' if unchanged != 1 else ''} unchanged.*")

        st.caption("Objective: minimised total absolute change from starting values (L1).")

    else:
        col1, col2 = st.columns(2)
        col1.metric("Mass balance", "❌", f"residual: {result.mass_residual:.3f} {unit}")
        col2.metric("Copper balance", "❌", f"residual: {result.copper_residual:.3f} {unit}")

        st.error("Cannot solve with current locks.")

        if result.unlock_suggestion is None:
            st.warning(
                "Too many locked conflicts. Review all locked rows."
            )
        else:
            n = len(result.unlock_suggestion)
            # Map row_id → name using pre_solve_materials
            id_to_name = {m.row_id: m.name for m in pre_solve_materials}
            row_labels = " → ".join(
                f"Row {rid} ({id_to_name.get(rid, '?')})"
                for rid in result.unlock_suggestion
            )
            if n == 1:
                st.info(f"Suggestion: unlock any one of: {row_labels}")
            else:
                st.info(f"Suggestion: unlock these {n} rows: {row_labels}")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="BOM Solver", layout="wide")

    # ---- Session state initialisation ----
    if "df" not in st.session_state:
        st.session_state.df = _make_default_df()
    if "unit" not in st.session_state:
        st.session_state.unit = "tonne"
    if "solve_result" not in st.session_state:
        st.session_state.solve_result = None
    if "pre_solve_materials" not in st.session_state:
        st.session_state.pre_solve_materials = None
    if "restore_prompted" not in st.session_state:
        st.session_state.restore_prompted = False
    if "last_saved_hash" not in st.session_state:
        st.session_state.last_saved_hash = None

    # ---- Autosave restore prompt (once per session) ----
    if not st.session_state.restore_prompted:
        saved = _load_autosave()
        if saved:
            age = _format_age(saved.get("saved_at", ""))
            st.info(f"A session from {age} was found.")
            col_r, col_d, _ = st.columns([1, 1, 6])
            if col_r.button("Restore", key="btn_restore"):
                raw_df = pd.DataFrame(saved.get("materials", []))
                st.session_state.df   = _normalise_df(raw_df)
                st.session_state.unit = saved.get("unit", "tonne")
                st.session_state.restore_prompted = True
                st.rerun()
            if col_d.button("Discard", key="btn_discard"):
                _delete_autosave()
                st.session_state.restore_prompted = True
                st.rerun()
        else:
            st.session_state.restore_prompted = True

    # ---- Header row ----
    hdr_left, hdr_right = st.columns([6, 2])
    hdr_left.title("BOM Mass & Copper Balance Solver")
    unit = hdr_right.selectbox(
        "Unit", UNITS,
        index=UNITS.index(st.session_state.unit),
        key="unit_selector",
        label_visibility="visible",
    )
    if unit != st.session_state.unit:
        st.session_state.unit = unit

    st.divider()

    # ---- Buttons ----
    df = _normalise_df(st.session_state.df)
    materials_for_validation = _df_to_materials(df, st.session_state.unit)
    validation_errors = validate_materials(materials_for_validation)
    has_errors = len(validation_errors) > 0

    btn_col1, btn_col2, btn_col3, _ = st.columns([1, 1.4, 1, 5])
    solve_clicked        = btn_col1.button("Solve ▶", disabled=has_errors, type="primary")
    clear_clicked        = btn_col2.button("Clear Solution")
    reset_clicked        = btn_col3.button("Reset All")

    # ---- Global validation banners (row_id=None) ----
    global_errors = [e for e in validation_errors if e.row_id is None]
    for err in global_errors:
        st.error(f"✖ {err.message}")

    # ---- Data editor ----
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "row_id": st.column_config.NumberColumn(
                "Row ID", disabled=True, width="small"
            ),
            "name": st.column_config.TextColumn(
                "Material", width="medium"
            ),
            "material_type": st.column_config.SelectboxColumn(
                "Type", options=MATERIAL_TYPES, width="small"
            ),
            "cu_pct": st.column_config.NumberColumn(
                "Cu %", min_value=0.0, max_value=100.0,
                format="%.2f", width="small"
            ),
            "cu_pct_locked": st.column_config.CheckboxColumn(
                "Cu%🔒", disabled=True, width="small"
            ),
            "quantity": st.column_config.NumberColumn(
                "Quantity", min_value=0.0, format="%.3f", width="small"
            ),
            "locked": st.column_config.CheckboxColumn(
                "🔒 Locked", width="small"
            ),
        },
        key="table_editor",
    )

    # Normalise and persist edits
    edited_df = _normalise_df(edited_df)
    st.session_state.df = edited_df

    # ---- Row-level validation errors (below table, grouped by row_id) ----
    row_errors = [e for e in validation_errors if e.row_id is not None]
    if row_errors:
        by_row: dict[int, list] = defaultdict(list)
        for err in row_errors:
            by_row[err.row_id].append(err)

        # Build name lookup
        id_to_name = {int(row["row_id"]): str(row["name"]) for _, row in edited_df.iterrows()}

        with st.expander("⚠ Validation errors", expanded=True):
            for rid in sorted(by_row.keys()):
                name = id_to_name.get(rid, "?")
                for err in by_row[rid]:
                    st.warning(f"⚠ Row {rid} ({name}): {err.message}")

    # ---- Autosave (debounced) ----
    current_hash = _df_hash(edited_df, st.session_state.unit)
    if current_hash != st.session_state.last_saved_hash:
        _save_autosave(edited_df, st.session_state.unit)
        st.session_state.last_saved_hash = current_hash

    # ---- Button actions ----
    if solve_clicked:
        materials = _df_to_materials(edited_df, st.session_state.unit)
        st.session_state.pre_solve_materials = materials
        result = solve(materials)
        st.session_state.solve_result = result

        if result.feasible:
            # Update df quantities for unlocked rows
            solved = result.quantities
            new_df = edited_df.copy()
            for i, row in new_df.iterrows():
                rid = int(row["row_id"])
                if not bool(row["locked"]) and rid in solved:
                    new_df.at[i, "quantity"] = solved[rid]
            st.session_state.df = new_df
        st.rerun()

    if clear_clicked:
        st.session_state.solve_result       = None
        st.session_state.pre_solve_materials = None
        st.rerun()

    if reset_clicked:
        st.session_state.df                  = _make_default_df()
        st.session_state.unit                = "tonne"
        st.session_state.solve_result        = None
        st.session_state.pre_solve_materials = None
        st.session_state.last_saved_hash     = None
        st.session_state.restore_prompted    = True
        _delete_autosave()
        st.rerun()

    # ---- Results panel ----
    if st.session_state.solve_result is not None:
        _render_results(
            st.session_state.solve_result,
            st.session_state.pre_solve_materials,
            st.session_state.unit,
        )


if __name__ == "__main__":
    main()
