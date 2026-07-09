# Soft Sensor Prediction System — FastAPI + React

An end-to-end industrial soft sensor platform: upload process data, clean it, run intelligent feature selection, train a model (Denoising Autoencoder or a classic ML baseline), evaluate predictions, and run what-if simulations.

This package contains the **FastAPI backend** and **React frontend** only. (There is also a legacy Streamlit UI in the original project that this handoff intentionally excludes — everything here is self-contained and does not depend on it.)

---

## Project Structure

```
Soft_Sensor_Handoff/
├── backend/                # FastAPI app
│   └── app/
│       ├── main.py         # App entry point, CORS, router registration
│       ├── api/routes/     # One router per feature area (datasets, preprocess, feature_selection, training, predict, overview, jobs)
│       ├── services/       # Business logic — wraps src/ for the API layer
│       ├── schemas/        # Pydantic request/response models
│       ├── jobs/           # Background job manager (polling-based long-running tasks)
│       └── core/config.py  # CORS origins, re-exports of config.settings
├── frontend/                # React + TypeScript + Vite app
│   └── src/
│       ├── pages/           # One folder per page (Upload, Preprocess, FeatureSelection, Train, Predict, Overview)
│       ├── components/      # Shared UI components (tables, charts, stepper, etc.)
│       ├── api/             # Axios client + typed API calls
│       └── state/           # React context for active dataset/project
├── src/                     # Framework-agnostic core logic (imported by the backend)
│   ├── data/                # SQLite dataset versioning + preprocessing pipeline
│   ├── feature_selection/   # 12-method consensus feature selection engine
│   ├── models/              # IndustrialDAE (PyTorch) + wrapper interfaces
│   ├── training/            # Training loops (DAE, sklearn, LSTM, Kalman)
│   ├── evaluation/          # RMSE / MAE / R² / MAPE metrics
│   ├── persistence/         # Model save/load
│   └── simulation/          # What-if sensitivity analysis
├── config/settings.py       # Single source of truth for paths, thresholds, hyperparameter defaults
├── docs/                    # Supplementary technical docs
├── sample_data/             # A sample dataset you can upload to try the app end-to-end
└── requirements.txt          # Python dependencies (backend + src)
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

- On first run, `dashboard.db` (SQLite) and `saved_models/` are created automatically — no manual setup needed.
- The API is served at `http://localhost:8010`, with routes under `/api/*` (e.g. `http://localhost:8010/api/health`).
- **Run this from the repo root**, not from inside `backend/` — `config.settings` uses paths relative to the working directory the process starts in.

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

1. Open `http://localhost:5173`.
2. Go to **Connect Process Data** → **Upload New Dataset** and upload `sample_data/Data_DAE.xlsx` (or your own `.xlsx`/`.csv`).
3. Walk through **Preprocessing** → **Feature Selection** → **Train Model** → **Predict** in order — the sidebar/stepper follows this flow.

## Production build (frontend)

```bash
cd frontend
npm run build
```

Outputs static files to `frontend/dist/`, which can be served by any static file host (or behind the FastAPI app / a reverse proxy) — point it at the same backend API.

---

## Key Features

- **Dataset versioning** — every upload is persisted (SQLite + Parquet); switch between historical versions at any time.
- **12-method consensus feature selection** — correlation, F-test, mutual information, RF/XGBoost/LightGBM importance, Lasso/Elastic Net, RFE/SFS/SBS, PCA loadings — with a confidence-scored recommendation (Highly Recommended / Recommended / Consider / Weak) and full per-feature reasoning.
- **Model training** — Denoising Autoencoder (PyTorch) plus Random Forest, XGBoost, LightGBM, LSTM, and Kalman Filter baselines, with auto-train mode and live loss curves.
- **Prediction & evaluation** — RMSE / MAE / R² / MAPE per target, actual-vs-predicted charts, residual analysis.
- **What-if sensitivity analysis** — sweep one or more input features and see the effect on each predicted KPI.

## Notes for whoever picks this up

- `src/` has no FastAPI or React imports — it's plain Python and can be tested/extended independently of either UI layer.
- All constants (paths, thresholds, hyperparameter defaults) live in `config/settings.py` — check there before hardcoding anything.
- Long-running operations (feature selection, training) run as background jobs polled via `/api/jobs/{id}` — see `backend/app/jobs/manager.py` and the frontend's `useJobPolling` hook.
