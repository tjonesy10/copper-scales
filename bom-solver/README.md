# BOM Mass & Copper Balance Solver

A local, browser-based Python app that lets you build a Bill of Materials and automatically compute quantities that satisfy both mass balance (total inputs equal total outputs) and copper balance (copper mass is conserved across inputs and outputs). Enter materials by hand, lock any quantities you want held fixed, and click Solve — the app finds the closest valid solution using a linear program that minimises total change from your starting values.

## Run instructions

```bash
# Install dependencies (requires uv)
cd bom-solver
uv sync

# Start the app
uv run streamlit run bom_solver/app.py

# Run tests
uv run pytest
```
