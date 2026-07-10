# SoftSense AI — Soft Sensor + What-If Studio (FastAPI + React)

An end-to-end industrial AI platform with two modules under one React app:

- **Soft Sensor Module** — upload process data, clean it, run intelligent feature selection, train a model (Denoising Autoencoder or a classic ML baseline), and evaluate predictions.
- **What-If Studio** — simulate hypothetical process scenarios against trained Kalman soft-sensor models: override any input tag, instantly see the predicted effect on 14 KPIs and compressor power/constraint limits, and validate against historical data.

The FastAPI backend and React frontend are self-contained. `Scripts/` also contains a standalone legacy Streamlit **What-If Analysis** app — it is the read-only functional reference the What-If Studio module was ported from, is never imported by the backend, and is not required to run this app.

---

## Project Structure

```
Soft_Sensor_and_What_If_Platform/
├── backend/                # FastAPI app
│   └── app/
│       ├── main.py         # App entry point, CORS, router registration
│       ├── api/routes/     # One router per feature area (datasets, preprocess, feature_selection, training, predict, overview, jobs, what_if)
│       ├── services/       # Business logic — wraps src/ for the API layer
│       ├── schemas/        # Pydantic request/response models
│       ├── jobs/           # Background job manager (polling-based long-running tasks)
│       └── core/config.py  # CORS origins, re-exports of config.settings
├── frontend/                # React + TypeScript + Vite app
│   └── src/
│       ├── pages/
│       │   ├── Overview/        # Whole-app landing page ('/')
│       │   ├── SoftSensor/       # Soft Sensor module's own overview ('/soft-sensor-overview')
│       │   ├── Upload/, Preprocess/, FeatureSelection/, Train/, Predict/   # Soft Sensor workflow pages
│       │   └── WhatIf/          # What-If Studio: Overview, Case Setup, Dashboard + their sub-components
│       ├── components/      # Shared UI components (tables, charts, stepper, etc.) — no UI/chart library, all hand-rolled
│       ├── api/             # Axios client + typed API calls (one file per backend domain, incl. whatIf.ts)
│       └── state/           # React context for active dataset/project/What-If wizard tags
├── src/                     # Framework-agnostic core logic (imported by the backend, no FastAPI/React/Streamlit imports)
│   ├── data/                # SQLite dataset versioning + preprocessing pipeline
│   ├── feature_selection/   # 12-method consensus feature selection engine
│   ├── models/              # IndustrialDAE (PyTorch) + wrapper interfaces
│   ├── training/            # Training loops (DAE, sklearn, LSTM, Kalman)
│   ├── evaluation/          # RMSE / MAE / R² / MAPE metrics
│   ├── persistence/         # Model save/load (saved_models/)
│   ├── simulation/          # Orphaned generic sweep helper — unrelated to What-If Studio, kept for backward compatibility
│   └── whatif/              # What-If Studio engine: config_io, historian, engine (Kalman/CoolProp/optimization pipeline), wizard, model_status
├── Scripts/                 # Standalone legacy Streamlit What-If app — READ-ONLY reference for src/whatif/, not run by this app
├── Data/                    # What-If Studio inputs: Config_file.xlsx, DMC_Screen_tags_data.xlsx
├── Results/                 # What-If Studio inputs/outputs: Model/*.pkl (trained Kalman models+scalers), historian workbook
├── config/settings.py       # Single source of truth for paths, thresholds, hyperparameter defaults (incl. WHATIF_* paths)
├── docs/                    # Supplementary technical docs
├── sample_data/             # A sample dataset you can upload to try the Soft Sensor module end-to-end
└── requirements.txt          # Python dependencies (backend + src, incl. CoolProp/nfoursid for What-If Studio)
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm

---

## 1. Backend setup (FastAPI)

From the root of this folder:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

uvicorn backend.app.main:app --reload --port 8010
```

- On first run, `dashboard.db` (SQLite) and `saved_models/` are created automatically — no manual setup needed for the Soft Sensor module.
- **What-If Studio** needs its input files already in place: `Data/Config_file.xlsx`, `Data/DMC_Screen_tags_data.xlsx`, `Results/Model/*.pkl` (trained Kalman models + scalers), and `Results/Raw_data_plus_simulated_data.xlsx` (historian). These ship with this repo; there's no upload/train flow for them in Phase 1 — see [What-If Studio](#what-if-studio-details) below.
- The API is served at `http://localhost:8010`, with routes under `/api/*` (e.g. `http://localhost:8010/api/health`, `/api/what-if/*`).
- **Run this from the repo root**, not from inside `backend/` — `config.settings` and `src/whatif/paths.py` use paths relative to the repo root.

## 2. Frontend setup (React + Vite)

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

- Opens at `http://localhost:5173`.
- The dev server proxies `/api` requests to `http://localhost:8010` (see `frontend/vite.config.ts`) — make sure the backend is running first.
- The backend's CORS allow-list only includes `http://localhost:5173` (see `backend/app/core/config.py`). If you run the frontend on a different port, add it there.

## 3. Try it out

**Soft Sensor Module:**
1. Open `http://localhost:5173`.
2. Go to **Soft Sensor Module → Connect Process Data** → **Upload New Dataset** and upload `sample_data/Data_DAE.xlsx` (or your own `.xlsx`/`.csv`).
3. Walk through **Preprocessing** → **Feature Selection** → **Train Model** → **Predict** in order — the sidebar/stepper follows this flow.

**What-If Studio:**
1. Go to **What-If Studio → Overview** for a quick orientation, then **Open Scenario Setup**.
2. On **What-If Case Setup**, confirm the config/model status cards are green (they read the bundled `Data/`/`Results/` files), optionally run the Plant Configuration Wizard, then **Proceed to What-If Dashboard**.
3. On **What-If Dashboard**, pick a historical timestamp, optionally override an input tag, and **Compute What-If Scenario** to see KPI deltas, the actual-vs-estimated table, and historical validation filters.

## Production build (frontend)

```bash
cd frontend
npm run build
```

Outputs static files to `frontend/dist/`, which can be served by any static file host (or behind the FastAPI app / a reverse proxy) — point it at the same backend API.

---

## Key Features

### Soft Sensor Module

- **Dataset versioning** — every upload is persisted (SQLite + Parquet); switch between historical versions at any time.
- **12-method consensus feature selection** — correlation, F-test, mutual information, RF/XGBoost/LightGBM importance, Lasso/Elastic Net, RFE/SFS/SBS, PCA loadings — with a confidence-scored recommendation (Highly Recommended / Recommended / Consider / Weak) and full per-feature reasoning.
- **Model training** — Denoising Autoencoder (PyTorch) plus Random Forest, XGBoost, LightGBM, LSTM, and Kalman Filter baselines, with auto-train mode and live loss curves.
- **Prediction & evaluation** — RMSE / MAE / R² / MAPE per target, actual-vs-predicted charts, residual analysis.

### What-If Studio Details

- **Plant Configuration Wizard** — answer a few plant line-up questions (CGC/PRC/ERC stage counts, furnace count) and the PI tag mapping is auto-generated and filtered from the master tag dictionary.
- **Scenario simulation** — override any input tag within its safe operating range and run the full Kalman-filter/CoolProp-thermodynamics/optimization pipeline for a single historical snapshot in one call.
- **KPI comparison** — 14 key performance indicators shown actual-vs-estimated, plus a full parameter comparison table with change highlighting.
- **Constraint awareness** — a hard operating constraint (e.g. `CGC_5TH_STG_DISCH_PRES`) short-circuits the simulation with a clear message if tripped, exactly like the original engineering logic.
- **Historical validation** — filter the historian by 5 validation tags to cross-check a scenario against similar past operating snapshots, and export CSV.
- Business logic lives in `src/whatif/` — a from-scratch, Streamlit-free port of `Scripts/whatif_runner.py`'s pipeline (see that module's docstrings for what changed and why). Retraining the Kalman models (`Scripts/Model_development_and_static_whatif_testing.py`) is **not yet wired into this UI** — Phase 1 assumes the 48 `.pkl` artifacts under `Results/Model/` already exist.

## Notes for whoever picks this up

- `src/` has no FastAPI, React, or Streamlit imports — it's plain Python and can be tested/extended independently of any UI layer. This includes `src/whatif/`.
- All constants (paths, thresholds, hyperparameter defaults) live in `config/settings.py` — check there before hardcoding anything, including the `WHATIF_*` path constants.
- Long-running operations (feature selection, training) run as background jobs polled via `/api/jobs/{id}` — see `backend/app/jobs/manager.py` and the frontend's `useJobPolling` hook. What-If Studio's endpoints are all synchronous (a scenario run is fast enough not to need this).
- `src/simulation/what_if.py` is an older, unrelated generic sweep helper — it predates and is not used by What-If Studio; don't confuse the two when navigating the codebase.
- `Scripts/` (the legacy Streamlit What-If app) is read-only reference material and must not be modified — it stays in sync with nothing else in this repo and is kept only so `src/whatif/` can be checked against it.
