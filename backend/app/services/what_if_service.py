"""
backend/app/services/what_if_service.py
==========================================
Business orchestration for the What-If Analysis module. Every function
reloads config/historian fresh from disk per call (no server-side session —
see src/whatif/engine.py's docstring and the migration plan's statelessness
note); all math is delegated to src/whatif/*, which is never modified here.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import threading
import time
from typing import Any, Dict, List

import pandas as pd
from fastapi import HTTPException, UploadFile

from src.whatif import config_io, constants, engine, historian, model_status, paths, wizard
from src.whatif.config_io import WhatIfConfig

from backend.app.schemas import what_if as schemas


def _load_config() -> WhatIfConfig:
    path = paths.config_file()
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Config file not found at {path}")
    try:
        return config_io.load_all_config(path)
    except config_io.ConfigSchemaError as e:
        raise HTTPException(status_code=422, detail=str(e))


_historian_cache: Dict[str, Any] = {"path": None, "mtime": None, "df": None}
_historian_cache_lock = threading.Lock()


def _load_historian() -> pd.DataFrame:
    """Cached by (path, mtime): the historian is a ~7000-row/194-column
    Excel file that takes several seconds to parse via openpyxl on every
    call — unlike the small config workbook, that cost is too high to pay
    on every dashboard interaction. Every consumer (engine.whatif_analysis,
    get_dates/get_timestamps/get_baseline/run_validation_filter) only reads
    from the returned frame or works on an explicit .copy(), so a read-only
    cache is safe. Invalidates automatically if the file is replaced (e.g. a
    future retrain phase), since the check is keyed on mtime, not just path."""
    path = paths.historian_file()
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Historian file not found at {path}")
    mtime = os.path.getmtime(path)
    with _historian_cache_lock:
        if _historian_cache["path"] == path and _historian_cache["mtime"] == mtime:
            return _historian_cache["df"]
    df = historian.load_process_data(path)
    with _historian_cache_lock:
        _historian_cache["path"] = path
        _historian_cache["mtime"] = mtime
        _historian_cache["df"] = df
    return df


def _atomic_write_bytes(path: str, data: bytes) -> None:
    """Temp-file-then-os.replace() write, to avoid a concurrent reader seeing
    a partially-written file. There is still no cross-request lock — Phase 1
    assumes a single engineer configuring at a time (documented limitation).

    On Windows, os.replace() can fail with PermissionError/WinError 5 if the
    destination is transiently locked by another process (Excel has it open,
    antivirus scanning it, OneDrive/cloud-sync briefly holding it if this repo
    lives under a synced folder like Desktop) — even though the file was fully
    readable moments earlier. That's a real, observed failure mode here (not
    hypothetical), so retry briefly before giving up rather than surfacing an
    opaque, uncaught 500 to the caller."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp_", suffix=os.path.splitext(path)[1])
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        last_error: OSError | None = None
        for attempt in range(5):
            try:
                os.replace(tmp_path, path)
                return
            except OSError as e:
                last_error = e
                time.sleep(0.2 * (attempt + 1))
        raise last_error
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Config status / PI mapping / model mapping
# ---------------------------------------------------------------------------

def get_config_status() -> schemas.ConfigStatusResponse:
    path = paths.config_file()
    if not os.path.isfile(path):
        return schemas.ConfigStatusResponse(
            pi_mapping_present=False, pi_mapping_row_count=0,
            model_details_present=False, model_details_row_count=0, source_path=None,
        )
    cfg = _load_config()
    return schemas.ConfigStatusResponse(
        pi_mapping_present=not cfg.pi_names_df.empty,
        pi_mapping_row_count=len(cfg.pi_names_df),
        model_details_present=not cfg.model_details_df.empty,
        model_details_row_count=len(cfg.model_details_df),
        source_path=path,
    )


def get_pi_mapping() -> schemas.RowsResponse:
    cfg = _load_config()
    normalized = wizard.normalize_pi_df(cfg.pi_names_df)
    rows = json.loads(normalized.to_json(orient="records")) if not normalized.empty else []
    return schemas.RowsResponse(rows=rows)


async def upload_config(file: UploadFile) -> schemas.ConfigStatusResponse:
    data = await file.read()
    try:
        pd.ExcelFile(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not parse workbook: {e}")
    try:
        _atomic_write_bytes(paths.config_file(), data)
    except OSError as e:
        raise HTTPException(
            status_code=409,
            detail=(
                f"The workbook was read successfully, but saving it to {paths.config_file()} failed: {e}. "
                "This usually means the file is currently open in Excel or being synced by OneDrive/cloud "
                "storage — close it and try again."
            ),
        )
    return get_config_status()


def get_detected_counts() -> schemas.DetectedCountsResponse:
    cfg = _load_config()
    pi_norm = wizard.normalize_pi_df(cfg.pi_names_df)
    cgc = wizard.available_stages(pi_norm, "CGC")
    prc = wizard.available_stages(pi_norm, "PRC")
    erc = wizard.available_stages(pi_norm, "ERC")
    furnaces = wizard.available_furnaces(pi_norm)
    return schemas.DetectedCountsResponse(
        cgc_max=max(cgc) if cgc else 0,
        prc_max=max(prc) if prc else 0,
        erc_max=max(erc) if erc else 0,
        furnace_max=max(furnaces) if furnaces else 0,
    )


def generate_mapping(body: schemas.GenerateMappingRequest) -> schemas.GenerateMappingResponse:
    cfg = _load_config()
    pi_norm = wizard.normalize_pi_df(cfg.pi_names_df)
    cgc_all = wizard.available_stages(pi_norm, "CGC")
    prc_all = wizard.available_stages(pi_norm, "PRC")
    erc_all = wizard.available_stages(pi_norm, "ERC")
    furnace_all = wizard.available_furnaces(pi_norm)

    cgc_stages = [s for s in cgc_all if s <= body.cgc_stages]
    prc_stages = [s for s in prc_all if s <= body.prc_stages]
    erc_stages = [s for s in erc_all if s <= body.erc_stages]
    furnaces = [f for f in furnace_all if f <= body.furnaces]

    mapping = wizard.generate_pi_mapping(pi_norm, cgc_stages, prc_stages, erc_stages, furnaces)
    section_counts: Dict[str, int] = (
        {k: int(v) for k, v in mapping.groupby("Section").size().to_dict().items()}
        if not mapping.empty else {}
    )

    return schemas.GenerateMappingResponse(
        rows=json.loads(mapping.to_json(orient="records")) if not mapping.empty else [],
        section_counts=section_counts,
        wizard_selection={
            "cgc_stages_answered": body.cgc_stages, "prc_stages_answered": body.prc_stages,
            "erc_stages_answered": body.erc_stages, "furnaces_answered": body.furnaces,
            "cgc_stages_kept": cgc_stages, "prc_stages_kept": prc_stages,
            "erc_stages_kept": erc_stages, "furnaces_kept": furnaces,
        },
    )


def commit_mapping(body: schemas.MappingRowsRequest) -> schemas.RowsResponse:
    """Stateless in Phase 1: validates/normalizes and echoes the edited grid
    back. There's no server-side session to persist into — the client carries
    the committed rows forward to whichever endpoint needs them next (e.g.
    config/export)."""
    df = pd.DataFrame(body.rows)
    if df.empty:
        return schemas.RowsResponse(rows=[])
    normalized = wizard.normalize_pi_df(df)
    return schemas.RowsResponse(rows=json.loads(normalized.to_json(orient="records")) if not normalized.empty else [])


def get_model_mapping() -> schemas.ModelMappingResponse:
    cfg = _load_config()
    df = _load_historian()
    return schemas.ModelMappingResponse(
        rows=json.loads(cfg.model_details_df.to_json(orient="records")) if not cfg.model_details_df.empty else [],
        historian_tags=sorted(df.columns.astype(str).tolist()),
    )


def commit_model_mapping(body: schemas.MappingRowsRequest) -> schemas.RowsResponse:
    return schemas.RowsResponse(rows=body.rows)


def export_config(body: schemas.ConfigExportRequest):
    pi_df = pd.DataFrame(body.pi_mapping_rows)
    model_df = pd.DataFrame(body.model_details_rows)

    if body.format == "csv":
        buf = io.StringIO()
        pi_df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8"), "text/csv", "Generated_PI_mapping.csv"

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pi_df.to_excel(writer, sheet_name="PI_generalised_Name", index=False)
        model_df.to_excel(writer, sheet_name="Model details", index=False)
    return (
        buf.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Config_file.xlsx",
    )


async def upload_training_data(file: UploadFile) -> schemas.TrainingDataUploadResponse:
    data = await file.read()
    try:
        xl = pd.ExcelFile(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not parse workbook: {e}")

    required = ["PI data", "Furnace data"]
    missing = [s for s in required if s not in xl.sheet_names]
    if missing:
        return schemas.TrainingDataUploadResponse(
            saved=False, sheets_found=list(xl.sheet_names), missing_sheets=missing,
        )

    try:
        _atomic_write_bytes(paths.training_workbook(), data)
    except OSError as e:
        raise HTTPException(
            status_code=409,
            detail=(
                f"The workbook was read successfully, but saving it to {paths.training_workbook()} failed: {e}. "
                "This usually means the file is currently open in Excel or being synced by OneDrive/cloud "
                "storage — close it and try again."
            ),
        )
    return schemas.TrainingDataUploadResponse(saved=True, sheets_found=list(xl.sheet_names), missing_sheets=[])


def get_models_status() -> schemas.ModelStatusResponse:
    status = model_status.check_models_trained(paths.model_dir())
    return schemas.ModelStatusResponse(
        all_present=status.all_present, tags_ok=status.tags_ok,
        tags_missing=status.tags_missing, pkl_count=status.pkl_count,
    )


# ---------------------------------------------------------------------------
# Dashboard: tag resolution, timestamps, baseline, scenario compute
# ---------------------------------------------------------------------------

def _limits_for(tags: List[str], df: pd.DataFrame, cfg: WhatIfConfig) -> Dict[str, Dict[str, float]]:
    """Config-sheet limits first, historical min/max as fallback (ported from
    Whatif_streamlit_dashboard.py's _limits_for)."""
    config_limits: Dict[str, Any] = {}
    ui = cfg.user_inputs_df
    if {"Parameter", "Lower Limit", "Upper Limit"}.issubset(ui.columns):
        dl = ui.copy()
        dl["Parameter"] = dl["Parameter"].astype(str).str.strip()
        dl = dl[dl["Parameter"].str.lower() != "nan"]
        config_limits = dl.set_index("Parameter")[["Lower Limit", "Upper Limit"]].to_dict("index")

    out: Dict[str, Dict[str, float]] = {}
    for tag in tags:
        cfg_lim = config_limits.get(tag)
        lo = pd.to_numeric(pd.Series([cfg_lim.get("Lower Limit")]), errors="coerce").iloc[0] if cfg_lim else None
        hi = pd.to_numeric(pd.Series([cfg_lim.get("Upper Limit")]), errors="coerce").iloc[0] if cfg_lim else None
        if pd.notna(lo) and pd.notna(hi):
            out[tag] = {"lower": float(lo), "upper": float(hi)}
        elif tag in df.columns and pd.api.types.is_numeric_dtype(df[tag]):
            out[tag] = {"lower": float(df[tag].min()), "upper": float(df[tag].max())}
        else:
            out[tag] = {"lower": 0.0, "upper": 1e6}
    return out


def get_tag_options(body: schemas.TagOptionsRequest) -> schemas.TagOptionsResponse:
    """3-tier source resolution: wizard-generated tags -> config 'user inputs'
    sheet -> full historian dropdown fallback (ported from the dashboard tab's
    Source A/B/C logic)."""
    cfg = _load_config()
    df = _load_historian()
    all_tags = sorted(df.columns.astype(str).tolist())

    generated_tags = sorted(t for t in body.generated_tags if t in df.columns)

    ui = cfg.user_inputs_df
    config_tags: List[str] = []
    if {"Parameter", "Lower Limit", "Upper Limit"}.issubset(ui.columns):
        dl = ui.copy()
        dl["Parameter"] = dl["Parameter"].astype(str).str.strip()
        config_tags = [t for t in dl["Parameter"].tolist() if t.lower() != "nan"]

    if generated_tags:
        source, tags = "wizard", generated_tags
    elif config_tags:
        source, tags = "config", config_tags
    else:
        source, tags = "historian", []

    limits = _limits_for(tags, df, cfg)
    return schemas.TagOptionsResponse(tags=tags, all_tags=all_tags, source=source, limits=limits)


def get_dates() -> schemas.DatesResponse:
    df = _load_historian()
    dates = sorted(pd.Series(df.index.date).unique())
    return schemas.DatesResponse(dates=[d.isoformat() for d in dates])


def get_timestamps(date: str) -> schemas.TimestampsResponse:
    df = _load_historian()
    try:
        target = pd.Timestamp(date).date()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date: {date}")
    stamps = sorted(df.index[df.index.date == target])
    return schemas.TimestampsResponse(timestamps=[ts.strftime("%Y-%m-%d %H:%M:%S") for ts in stamps])


def get_baseline(timestamp: str, tags: List[str]) -> schemas.BaselineResponse:
    df = _load_historian()
    ts = pd.Timestamp(timestamp)
    if ts not in df.index:
        raise HTTPException(status_code=404, detail=f"Timestamp {timestamp} not found in historian.")
    active_tags = [t for t in tags if t in df.columns] or df.columns.tolist()
    row = df.loc[[ts], active_tags].T
    row.columns = ["value"]
    values: Dict[str, Any] = {}
    for tag, val in row["value"].items():
        if pd.isna(val):
            values[tag] = None
            continue
        try:
            values[tag] = float(val)
        except (TypeError, ValueError):
            values[tag] = str(val)
    return schemas.BaselineResponse(values=values)


def run_scenario(body: schemas.WhatIfScenarioRequest) -> schemas.WhatIfScenarioResponse:
    """The core call: loads historian + config once, runs whatif_analysis()
    exactly once. Never decomposed into per-tag endpoints — the pipeline is
    order-dependent with a mid-pipeline constraint short-circuit."""
    df = _load_historian()
    cfg = _load_config()
    try:
        ts = pd.Timestamp(body.timestamp)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid timestamp: {body.timestamp}")
    if ts not in df.index:
        raise HTTPException(status_code=404, detail=f"Timestamp {body.timestamp} not found in historian.")

    user_input_df = pd.DataFrame(
        [{"Parameter": o.parameter, "Value": o.value} for o in body.overrides],
        columns=["Parameter", "Value"],
    )

    output_path = None
    if body.write_actual_vs_estimated_xlsx:
        output_path = paths.actual_vs_estimated_file(ts.strftime("%Y%m%d_%H%M%S"))

    try:
        result = engine.whatif_analysis(
            df, ts, user_input_df, cfg, paths.model_dir(),
            write_actual_vs_estimated_xlsx=body.write_actual_vs_estimated_xlsx,
            output_path=output_path,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=f"A required model artifact is missing: {e}")

    all_keys = sorted(set(result.actual.keys()) | set(result.estimated.keys()))
    rows: List[schemas.WhatIfScenarioRow] = []
    for key in all_keys:
        if key == "Timestamp":
            continue
        act = result.actual.get(key)
        est = result.estimated.get(key)
        try:
            change = float(est) - float(act)
        except (TypeError, ValueError):
            change = None
        rows.append(schemas.WhatIfScenarioRow(parameter=key, actual=act, estimated=est, change=change))

    kpis: List[schemas.WhatIfKpi] = []
    for tag in constants.KPI_TAGS:
        try:
            act_f = float(result.actual.get(tag))
            est_f = float(result.estimated.get(tag))
        except (TypeError, ValueError):
            continue
        kpis.append(schemas.WhatIfKpi(tag=tag, actual=act_f, estimated=est_f, change=est_f - act_f))

    return schemas.WhatIfScenarioResponse(
        constraint_hit=result.constraint_hit,
        constraint_message=result.constraint_message,
        rows=rows,
        kpis=kpis,
    )


def run_validation_filter(body: schemas.ValidationFilterRequest) -> schemas.ValidationFilterResponse:
    df = _load_historian()
    available = [t for t in constants.VALIDATION_TAGS if t in df.columns]
    filtered = df.copy()
    for tag in available:
        criterion = body.filters.get(tag)
        if criterion is None:
            continue
        if pd.api.types.is_numeric_dtype(filtered[tag]):
            lo = criterion.min if criterion.min is not None else float(df[tag].min())
            hi = criterion.max if criterion.max is not None else float(df[tag].max())
            filtered = filtered[(filtered[tag] >= lo) & (filtered[tag] <= hi)]
        elif criterion.values is not None:
            filtered = filtered[filtered[tag].isin(criterion.values)]

    display = filtered[available].reset_index() if available else filtered.reset_index()
    rows = json.loads(display.to_json(orient="records", date_format="iso"))
    return schemas.ValidationFilterResponse(rows=rows, match_count=len(filtered))


def export_scenario_csv(body: "schemas.WhatIfExportCsvRequest"):
    """Merged scenario + validation CSV export. Simplified relative to the
    original's pandas merge-on-Parameter (which joined a transposed scenario
    table against a transposed validation table): here the two tables are
    written as clearly-labeled sections in one CSV, since the client already
    has both JSON payloads and a literal structural merge would be fragile to
    reproduce exactly server-side without re-deriving the original's index
    alignment assumptions."""
    scenario_df = pd.DataFrame([r.model_dump() for r in body.rows])
    scenario_df.insert(0, "Selected Timestamp", body.timestamp)

    buf = io.StringIO()
    scenario_df.to_csv(buf, index=False)
    if body.validation_rows:
        buf.write("\nHistorical Validation Matches\n")
        pd.DataFrame(body.validation_rows).to_csv(buf, index=False)

    filename = "filtered_validation_data.csv" if body.validation_rows else "WhatIf_Result.csv"
    return buf.getvalue().encode("utf-8"), "text/csv", filename
