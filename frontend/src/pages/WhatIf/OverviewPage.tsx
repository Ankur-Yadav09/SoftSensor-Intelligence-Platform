import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

interface WorkflowStep {
  step: number
  icon: string
  title: string
  description: string
}

const WORKFLOW_STEPS: WorkflowStep[] = [
  { step: 1, icon: '🧙', title: 'Configure Scenario', description: 'Pick your plant line-up and confirm the tag mapping is ready.' },
  { step: 2, icon: '🚀', title: 'Run Simulation', description: 'Override any process variable and compute the predicted outcome.' },
  { step: 3, icon: '📊', title: 'Compare & Validate Results', description: 'Check KPI deltas against baseline and similar historical snapshots.' },
]

interface FeatureCard {
  icon: string
  title: string
  description: string
}

const FEATURES: FeatureCard[] = [
  { icon: '🎛️', title: 'Modify Process Variables', description: 'Override any input tag within its safe operating range.' },
  { icon: '🔮', title: 'Predict Process KPIs', description: 'See the effect on 14 key performance indicators instantly.' },
  { icon: '⚖️', title: 'Compare Baseline vs Scenario', description: 'Actual vs estimated, side by side, with change highlighting.' },
  { icon: '🔍', title: 'Validate Using Historical Data', description: 'Cross-check results against similar past operating snapshots.' },
]

interface ChecklistItem {
  icon: string
  title: string
  description: string
}

const PREREQUISITES: ChecklistItem[] = [
  { icon: '🧠', title: 'Trained Soft Sensor / Kalman Models', description: 'Results/Model — one Kalman model + 2 scalers per predicted parameter.' },
  { icon: '🗂️', title: 'Configuration File', description: 'Data/Config_file.xlsx — PI tag mapping, model inputs, limits, and constraints.' },
  { icon: '📈', title: 'Historical Process Data', description: 'Results/Raw_data_plus_simulated_data.xlsx — baseline snapshots to simulate from.' },
]

function WorkflowStepCard({ step }: { step: WorkflowStep }) {
  return (
    <div className="card" style={{ flex: 1, minWidth: 200, padding: '1.25rem', position: 'relative' }}>
      <div
        style={{
          width: 30,
          height: 30,
          borderRadius: 999,
          background: 'var(--primary)',
          color: 'white',
          fontWeight: 700,
          fontSize: '0.85rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '0.6rem',
        }}
      >
        {step.step}
      </div>
      <div style={{ fontSize: '1.4rem', marginBottom: '0.3rem' }}>{step.icon}</div>
      <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>{step.title}</div>
      <p className="caption" style={{ margin: 0 }}>{step.description}</p>
    </div>
  )
}

function FeatureCardView({ feature }: { feature: FeatureCard }) {
  return (
    <div className="status-card" style={{ flex: 1, minWidth: 220 }}>
      <div style={{ fontSize: '1.3rem', marginBottom: '0.4rem' }}>{feature.icon}</div>
      <div style={{ fontWeight: 700, marginBottom: '0.2rem', fontSize: '0.95rem' }}>{feature.title}</div>
      <p className="caption" style={{ margin: 0 }}>{feature.description}</p>
    </div>
  )
}

// Static landing page for the What-If Studio module — the entry point into
// Scenario Analysis, not a documentation page. Business logic/workflow is
// unchanged; only presentation (hero, workflow cards, feature cards,
// checklist, collapsible help) was redesigned.
export function WhatIfOverviewPage() {
  const navigate = useNavigate()
  const [helpOpen, setHelpOpen] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Hero */}
      <div className="section-banner" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span className="icon">🧭</span>
          <div>
            <h2 style={{ marginBottom: '0.3rem' }}>What-If Studio</h2>
            <p style={{ maxWidth: 640 }}>
              Scenario Analysis lets Process Engineers simulate hypothetical changes to process variables — before
              touching the real plant — and instantly see the predicted impact on key KPIs, compressor power, and
              constraint limits, using the same trained soft-sensor models behind SoftSense AI.
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button onClick={() => navigate('/what-if/case-setup')}>Open Scenario Setup →</button>
          <button className="chip" onClick={() => navigate('/what-if/dashboard')}>
            View Sample Scenario
          </button>
        </div>
      </div>

      {/* Workflow */}
      <div>
        <h3 style={{ marginBottom: '0.9rem' }}>How it works</h3>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          {WORKFLOW_STEPS.map((step) => (
            <WorkflowStepCard key={step.step} step={step} />
          ))}
        </div>
      </div>

      {/* Feature highlights */}
      <div>
        <h3 style={{ marginBottom: '0.9rem' }}>Key capabilities</h3>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          {FEATURES.map((f) => (
            <FeatureCardView key={f.title} feature={f} />
          ))}
        </div>
      </div>

      {/* Before you start */}
      <div className="card" style={{ padding: '1.5rem' }}>
        <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>✅ Before You Start</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
          {PREREQUISITES.map((item) => (
            <div key={item.title} style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <span style={{ fontSize: '1.2rem' }}>{item.icon}</span>
              <div>
                <div style={{ fontWeight: 600 }}>{item.title}</div>
                <p className="caption" style={{ margin: 0 }}>{item.description}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="caption" style={{ marginTop: '1rem' }}>
          All three are checked automatically on the What-If Case Setup page.
        </p>
      </div>

      {/* Need help — collapsible */}
      <div className="card" style={{ padding: '1.5rem' }}>
        <button className="chip" onClick={() => setHelpOpen((o) => !o)} style={{ width: '100%', textAlign: 'left' }}>
          {helpOpen ? '▲' : '▼'} Need help?
        </button>
        {helpOpen && (
          <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <p className="caption" style={{ margin: 0 }}>
              <strong>Dashboard is locked?</strong> Go to What-If Case Setup — it unlocks once the PI Tag Mapping,
              Model Mapping, and all trained Kalman models are detected.
            </p>
            <p className="caption" style={{ margin: 0 }}>
              <strong>Scenario failed to compute?</strong> Confirm the historical timestamp you picked has complete
              data, and that any overrides are within the displayed boundary range.
            </p>
            <p className="caption" style={{ margin: 0 }}>
              <strong>Validation table is empty?</strong> Widen the min/max filters — they default to the full
              historical range but can be narrowed by hand.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
