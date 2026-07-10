# SoftSense AI — Codebase Architecture & Workflow

A reference for *how the code is organized and how a request flows through it*. For setup/run instructions, see [`README.md`](./README.md).

---

## 1. The three layers

```
frontend/          React + TypeScript + Vite (dev server, default port 5173)
        ↕ HTTP (axios, proxied through /api)
backend/app/        FastAPI (port 8010)
        ↕ plain Python function calls
src/                Framework-agnostic business logic
        ↕ reads/writes
dashboard.db, saved_models/, Data/, Results/     Persistence (SQLite, pickles, Excel)
```

**The core rule: `src/` never imports FastAPI or React.** It's plain Python — testable and reusable independent of any UI. Everything web-specific (routes, request/response shaping, HTTP concerns) lives in `backend/app/`. Everything browser-specific (components, state, styling) lives in `frontend/src/`.

This is why the repo could support two very different frontends historically (a legacy Streamlit app in `Scripts/`, now read-only reference material, and the current React app) against the same `src/` logic.

---

## 2. Backend pattern: routes → schemas → services → src

Every backend feature follows the same 4-layer flow. Worked example — **Predict**:

1. **`backend/app/api/routes/predict.py`** — thin FastAPI route. Parses/validates the request, calls exactly one service function, returns its result.
2. **`backend/app/schemas/predict.py`** — Pydantic models for the request/response shape (`PredictRequest`, `PredictResponse`).
3. **`backend/app/services/predict_service.py`** — the orchestrator. Loads whatever it needs (model, dataset), calls into `src/`, reshapes the result into a plain dict/response model. This is where "business logic wiring" lives — not business logic itself.
4. **`src/persistence/model_store.py`**, **`src/models/wrappers.py`**, etc. — the actual math/IO. Zero knowledge that a web framework exists.

`backend/app/main.py` wires every route module together:
```python
app.include_router(predict.router, prefix="/api")
app.include_router(what_if.router, prefix="/api")
# ...
```

**Long-running work doesn't block the request.** Training and feature selection use `backend/app/jobs/manager.py` — a `ThreadPoolExecutor`-backed singleton (`job_manager`). The route calls `job_manager.submit(fn, ...)`, gets a `job_id` back immediately, and the frontend polls `GET /api/jobs/{id}` (via the `useJobPolling` hook) until `done: true`. Fast operations (predict, What-If scenario compute) skip this and respond synchronously.

---

## 3. Frontend pattern: page → api client → axios → backend

- **`frontend/src/api/*.ts`** — one file per backend domain (`predict.ts`, `training.ts`, `whatIf.ts`, ...). Each is a thin, typed wrapper around the shared `apiClient` (`api/client.ts` — axios, `baseURL: '/api'`). In dev, `vite.config.ts` proxies `/api` to `http://localhost:8010`.
- **`frontend/src/pages/<Feature>/<Feature>Page.tsx`** — a page composes: React Query `useQuery`/`useMutation` calls into the API layer, local `useState` for form/UI state, and shared components from `frontend/src/components/` (`Callout`, `DataTable`, `StatusCard`, `Tabs`, `MultiSelectDropdown`, `LineChart`/`ScatterChart`, ...) for layout.
- **`frontend/src/state/*Context.tsx`** — the only "global" client state: small `localStorage`-backed React Contexts for the few things that must survive page navigation (active dataset, active project, the What-If wizard's generated tag list).
- **`frontend/src/layout/Sidebar.tsx`** + **`routes.tsx`** — the navigation shell. Each sidebar entry maps 1:1 to a route.

**Notable constraint:** no UI component library (no MUI/AntD/Tailwind) and no charting library. Everything is hand-rolled CSS (`theme.css`, CSS custom properties) and custom SVG chart components. New pages should follow this convention rather than introducing a library.

---

## 4. Two modules, one shape

| | **Soft Sensor Module** | **What-If Studio** |
|---|---|---|
| Sidebar flow | Connect Data → Data Health → Feature Discovery → Build Model → Prediction | Overview → What-If Case Setup → What-If Dashboard |
| Frontend pages | `pages/Upload/`, `Preprocess/`, `FeatureSelection/`, `Train/`, `Predict/` | `pages/WhatIf/` |
| Backend routes | `datasets.py`, `preprocess.py`, `feature_selection.py`, `training.py`, `predict.py` | `what_if.py` |
| Core `src/` logic | `src/data/`, `src/feature_selection/`, `src/training/`, `src/models/`, `src/evaluation/` | `src/whatif/` (`config_io.py`, `historian.py`, `engine.py`, `wizard.py`, `model_status.py`) |
| Persistence | `dashboard.db` (SQLite) + `saved_models/` (pickled models/scalers) | `Data/Config_file.xlsx`, `Results/Model/*.pkl`, `Results/Raw_data_plus_simulated_data.xlsx` — a separate, file-based world, deliberately not merged into `dashboard.db` |
| Reference implementation | — (built directly against this architecture) | `Scripts/whatif_runner.py` + `Scripts/Whatif_streamlit_dashboard.py` — a **read-only** legacy Streamlit app `src/whatif/` was ported from. Never imported, never modified. |

Both modules use the exact same routes→schemas→services→src backend layering and the exact same page→api→component frontend layering described above — once you understand one, you understand the shape of the other.

---

## 5. One request, traced end-to-end

**What-If Studio's "Compute What-If Scenario" button:**

1. User clicks the button in `frontend/src/pages/WhatIf/DashboardPage.tsx` → calls `runScenario()` from `frontend/src/api/whatIf.ts`.
2. Axios POSTs to `/api/what-if/dashboard/compute` with a `WhatIfScenarioRequest` body (timestamp + overrides).
3. `backend/app/api/routes/what_if.py`'s `dashboard_compute()` route receives it, validated by the `schemas/what_if.py` Pydantic model, and calls `what_if_service.run_scenario(...)` — nothing else.
4. `backend/app/services/what_if_service.py` loads the historian and config (both cached in-process, keyed by file mtime, since the historian Excel file is expensive to parse) and calls `src/whatif/engine.py`'s `whatif_analysis()` — the actual Kalman-filter / CoolProp-thermodynamics / scipy-optimization pipeline. This function has no idea an HTTP request exists.
5. The service reshapes the returned `WhatIfResult` dataclass into a `WhatIfScenarioResponse` (rows + KPIs + constraint-hit flag); the route serializes it to JSON.
6. Back in `DashboardPage.tsx`, the `useMutation` resolves, and `KpiCardsRow`, `ActualVsEstimatedTable`, and `ValidationFiltersPanel` re-render with the new data.

Use this as a template: any other flow (upload a dataset, submit a training job, generate a PI mapping) follows the same six-step shape with different files at each step.

---

## 6. Where things live (quick map)

```
backend/app/
├── main.py              # router registration, CORS, startup hook
├── api/routes/          # one file per feature — thin, HTTP-only
├── schemas/              # Pydantic request/response models
├── services/              # orchestration — calls src/, shapes responses
├── jobs/manager.py       # background job submit()/get() for long-running work
└── core/config.py        # CORS origins + re-exports of config.settings

frontend/src/
├── api/                  # one .ts file per backend domain
├── pages/                # one folder per page, colocated sub-components
├── components/           # shared, hand-rolled UI (no library)
├── state/                # the few cross-page Contexts
├── layout/                # Sidebar + Layout shell
└── routes.tsx             # route table, one entry per sidebar item

src/
├── data/, feature_selection/, training/, models/, evaluation/, persistence/   # Soft Sensor logic
├── whatif/                # What-If Studio logic
└── simulation/what_if.py  # unrelated orphaned helper — not used by What-If Studio

config/settings.py         # single source of truth for all paths/thresholds/defaults
```

For the fully-annotated setup-oriented version of this tree (with install/run commands), see the **Project Structure** section of [`README.md`](./README.md).
