// Ported verbatim from Scripts/Whatif_streamlit_dashboard.py's KPI_TAGS / VALIDATION_TAGS
// (kept in sync with src/whatif/constants.py — mirrored, not shared, since the
// frontend is TypeScript and the backend is Python).

export const KPI_TAGS = [
  'DMCTF_feed', 'Quench_tower_overhead_temp', 'CGC_TURBINE_1_SPEED_(RPM)',
  'CGC_STAGE_1_SUCTION_PRESSURE', 'CGC_Power_KW', 'PRC_turbine_RPM',
  'PRC_1ST_STAGE_Suction_PRESSURE', 'PRC_Total_estimated_power_MW',
  'ERC_power', 'ERC_1ST_STAGE_Suction_PRESSURE', 'ERC_turbine_Speed',
  'Total_Power_(KW)', 'Total_required_steam_flow_(TPH)', 'Ethylene_product_flow',
]

export const VALIDATION_TAGS = [
  'DMCTF_feed', 'Quench_tower_overhead_temp', 'Fresh_ethane_feed',
  'fresh_feed_ethane_content', 'CGC_STAGE_1_SUCTION_PRESSURE',
]

export const SECTION_OPTIONS = ['', 'CGC', 'PRC', 'ERC', 'Furnace', 'Quench', 'Cold']
