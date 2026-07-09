import { Link } from 'react-router-dom'
import { Callout } from '../../components/Callout'

// Static how-to content, ported from Scripts/Whatif_streamlit_dashboard.py's
// "📖 Overview" tab. Step B is described as a status check rather than a
// "train models" action, per this module's Phase 1 scope (no retraining UI).
export function WhatIfOverviewPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div>
        <h1>📖 What-If Analysis — Overview</h1>
        <p className="caption">
          Simulate hypothetical process scenarios against the ethylene plant's trained Kalman soft-sensor models —
          override any input tag and see the effect on 14 key performance indicators, compressor power balances,
          and constraint limits.
        </p>
      </div>

      <div className="card" style={{ padding: '1.5rem' }}>
        <h3 style={{ marginTop: 0 }}>Prerequisites</h3>
        <ul>
          <li>
            A <code>Config_file.xlsx</code> under <code>Data/</code> defining the PI tag dictionary
            (<code>PI_generalised_Name</code>), model input mapping (<code>Model details</code>), operating limits
            (<code>user inputs</code>), and hard constraints (<code>Constraints</code>).
          </li>
          <li>
            Trained Kalman filter models and scalers under <code>Results/Model/</code> (48 files: one Kalman model
            + 2 scalers per predicted parameter).
          </li>
          <li>
            A historian file at <code>Results/Raw_data_plus_simulated_data.xlsx</code> providing baseline process
            snapshots to simulate from.
          </li>
        </ul>
      </div>

      <div className="card" style={{ padding: '1.5rem' }}>
        <h3 style={{ marginTop: 0 }}>Step-by-Step Workflow</h3>
        <ol>
          <li>
            <strong>What-If Case Setup</strong> — confirm the PI tag mapping and model mapping are loaded (or
            upload a config workbook to override), optionally run the Plant Configuration Wizard to auto-generate a
            mapping for your specific line-up, and confirm trained models are detected.
          </li>
          <li>
            <strong>What-If Dashboard</strong> — pick a historical snapshot, review the baseline values, override
            any input tag within its operating limits, and compute the scenario to see actual-vs-estimated KPIs and
            the full parameter comparison table.
          </li>
          <li>
            Optionally apply <strong>Validation Filters</strong> to cross-check the scenario against similar
            historical operating snapshots, and export results as CSV.
          </li>
        </ol>
      </div>

      <div className="card" style={{ padding: '1.5rem' }}>
        <h3 style={{ marginTop: 0 }}>Troubleshooting</h3>
        <Callout variant="info">
          If the What-If Dashboard shows it's locked, go to{' '}
          <Link to="/what-if/case-setup">What-If Case Setup</Link> — the dashboard unlocks once the PI Tag Mapping,
          Model Mapping, and all trained Kalman models are detected.
        </Callout>
      </div>
    </div>
  )
}
