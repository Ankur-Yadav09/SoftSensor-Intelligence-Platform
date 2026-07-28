import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  downloadBlob,
  exportFullConfig,
  getColumnOrder,
  getConfigStatus,
  getConstraints,
  getModelMapping,
  getModelsStatus,
  getMvDvCvTaglist,
  getPiMapping,
  getSectionOrder,
  getTargetSection,
  getUserInputs,
} from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { StatusCard } from '../../components/StatusCard'
import { useActiveWhatIf } from '../../state/ActiveWhatIfContext'

const WORKFLOW_STAGES = [
  { icon: '🧙', label: 'Configure' },
  { icon: '🚀', label: 'Run Scenario' },
  { icon: '⚖️', label: 'Compare Results' },
  { icon: '📤', label: 'Export Report' },
]

const GUIDE_SECTIONS = [
  {
    title: '🔧 System Config',
    items: [
      'Process Flow Order — plant sections in actual sequence, plus which one this case targets.',
      'PI Tag Mapping — raw PI tag → readable name → section.',
      'Input Tag Configuration (MV/DV/CV) (optional) — prioritized inputs for Model Mapping.',
    ],
  },
  {
    title: '🧠 Model Config',
    items: [
      'Connect Data, Data Health, AI Feature Discovery, Build Model, Experiment History — the shared Soft Sensor workflow, reused as-is.',
      'Model Mapping — predicted parameters and their model inputs.',
      'Generate What-If Models — upload training data and train (already-trained models are detected automatically).',
    ],
  },
  {
    title: '⚙️ What-If Config',
    items: [
      'Constraints (optional) — operating limits and bump/abort rules.',
      'User Inputs (optional) — overridable parameters with allowed ranges.',
      'Results Layout (optional) — display order for the results table.',
    ],
  },
]

const FAQ_ITEMS = [
  {
    q: 'What-If Analysis is locked?',
    a: 'Go to What-If Setup — it unlocks once PI Tag Mapping, Model Mapping, and all trained Kalman models are detected.',
  },
  {
    q: 'Scenario failed to compute?',
    a: 'Confirm the historical timestamp you picked has complete data, and that any overrides are within the displayed boundary range.',
  },
  {
    q: 'Validation table is empty?',
    a: 'Widen the min/max filters — they default to the full historical range but can be narrowed by hand.',
  },
]

function ResourceButton({
  icon,
  label,
  onClick,
  disabled,
  disabledHint,
}: {
  icon: string
  label: string
  onClick?: () => void
  disabled?: boolean
  disabledHint?: string
}) {
  return (
    <button
      className="chip"
      style={{ flex: 1, minWidth: 160, opacity: disabled ? 0.55 : 1 }}
      onClick={onClick}
      disabled={disabled}
      title={disabled ? disabledHint : undefined}
    >
      {icon} {label}
      {disabled && <span className="caption" style={{ display: 'block' }}>Coming soon</span>}
    </button>
  )
}

// Welcome page for What-If Studio — action-oriented landing screen (Quick
// Actions, workflow at a glance, live configuration readiness, resources)
// replacing the earlier text-heavy Overview page. Detailed step-by-step
// reference content still exists, just tucked behind the "User Guide"/"FAQ"
// resource buttons instead of being the default view.
export function WhatIfOverviewPage() {
  const navigate = useNavigate()
  const { targetSection } = useActiveWhatIf()
  const [guideOpen, setGuideOpen] = useState(false)
  const [faqOpen, setFaqOpen] = useState(false)

  const configStatusQuery = useQuery({ queryKey: ['whatif-config-status'], queryFn: getConfigStatus })
  const modelStatusQuery = useQuery({ queryKey: ['whatif-models-status'], queryFn: getModelsStatus })
  const targetSectionQuery = useQuery({ queryKey: ['whatif-target-section'], queryFn: getTargetSection })

  const piPresent = !!configStatusQuery.data?.pi_mapping_present
  const modelPresent = !!configStatusQuery.data?.model_details_present
  const sectionOrder = targetSectionQuery.data?.section_order ?? []
  const processOrderReady = sectionOrder.length >= 2
  const modelsReady = !!modelStatusQuery.data?.all_present

  const hasAnyConfig = piPresent || modelPresent || processOrderReady
  const fullyReady = processOrderReady && piPresent && modelPresent && modelsReady

  function startNewCase() {
    navigate('/what-if/case-setup?fresh=1')
  }

  function resumeCase() {
    navigate(fullyReady ? '/what-if/dashboard' : '/what-if/case-setup')
  }

  const downloadSampleMutation = useMutation({
    mutationFn: async () => {
      const [pi, model, sectionOrderRows, mvdvcv, constraints, userInputs, columnOrder, ts] = await Promise.all([
        getPiMapping(),
        getModelMapping(),
        getSectionOrder(),
        getMvDvCvTaglist(),
        getConstraints(),
        getUserInputs(),
        getColumnOrder(),
        getTargetSection(),
      ])
      const blob = await exportFullConfig({
        pi_mapping_rows: pi,
        model_details_rows: model.rows,
        constraints_rows: constraints,
        user_inputs_rows: userInputs,
        display_order_rows: columnOrder,
        section_order_rows: sectionOrderRows,
        mvdvcv_rows: mvdvcv,
        target_section: ts.target_section,
      })
      downloadBlob(blob, 'Sample_Config_file.xlsx')
    },
  })

  const statusTiles = [
    {
      label: 'Process Flow Order',
      ready: processOrderReady,
      value: processOrderReady ? `${sectionOrder.length} sections` : 'Not set',
    },
    {
      label: 'PI Tag Mapping',
      ready: piPresent,
      value: piPresent ? `${configStatusQuery.data?.pi_mapping_row_count ?? 0} tags` : 'Missing',
    },
    {
      label: 'Model Mapping',
      ready: modelPresent,
      value: modelPresent ? `${configStatusQuery.data?.model_details_row_count ?? 0} rows` : 'Missing',
    },
    {
      label: 'Trained Models',
      ready: modelsReady,
      value: modelStatusQuery.data ? `${modelStatusQuery.data.pkl_count}/${modelStatusQuery.data.required_pkl_count} files` : '—',
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Welcome + Quick Actions */}
      <div className="section-banner" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span className="icon">🧭</span>
          <div>
            <h2 style={{ marginBottom: '0.3rem' }}>Welcome to What-If Studio</h2>
            <p style={{ maxWidth: 620, margin: 0 }}>
              Simulate process scenarios against trained plant models and see the projected impact before you act.
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button onClick={startNewCase}>▶ Start New Case</button>
          <button
            className="chip"
            onClick={resumeCase}
            disabled={!hasAnyConfig}
            title={hasAnyConfig ? undefined : 'No existing configuration found yet'}
          >
            ⏩ Resume Existing Case
          </button>
        </div>
      </div>

      {/* Workflow at a glance */}
      <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', overflowX: 'auto' }}>
          {WORKFLOW_STAGES.map((stage, i) => (
            <div key={stage.label} style={{ display: 'flex', alignItems: 'center', flex: i === WORKFLOW_STAGES.length - 1 ? 'none' : 1 }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.4rem', minWidth: 120 }}>
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.1rem',
                    background: i === 0 ? 'linear-gradient(135deg, #4da6ff 0%, #2563eb 100%)' : 'var(--control-bg)',
                    color: i === 0 ? 'white' : 'var(--text-caption)',
                    border: i === 0 ? 'none' : '1px solid var(--border)',
                  }}
                >
                  {stage.icon}
                </div>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, textAlign: 'center' }}>{stage.label}</span>
              </div>
              {i < WORKFLOW_STAGES.length - 1 && (
                <div style={{ flex: 1, height: 2, background: 'var(--border)', marginBottom: '1.4rem' }} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Configuration status */}
      <div>
        <h3 style={{ marginBottom: '0.75rem' }}>Configuration Status</h3>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {statusTiles.map((t) => (
            <StatusCard
              key={t.label}
              label={t.label}
              value={t.value}
              sublabel={t.ready ? '✅ Ready' : '⏳ Pending'}
              tone={t.ready ? 'success' : 'warning'}
            />
          ))}
        </div>
      </div>

      {/* Current / recent case */}
      <div>
        <h3 style={{ marginBottom: '0.75rem' }}>Recent Cases</h3>
        {hasAnyConfig ? (
          <div className="card" style={{ padding: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <div style={{ fontWeight: 700 }}>Current configuration</div>
              <p className="caption" style={{ margin: 0 }}>
                Target section: {targetSection ?? targetSectionQuery.data?.target_section ?? 'not set'} ·{' '}
                {fullyReady ? 'Ready to run scenarios' : 'Setup in progress'}
              </p>
            </div>
            <button className="chip" onClick={resumeCase}>
              {fullyReady ? 'Go to What-If Analysis →' : 'Continue Setup →'}
            </button>
          </div>
        ) : (
          <p className="caption">No cases yet — click "Start New Case" above to begin.</p>
        )}
      </div>

      {/* Resources */}
      <div>
        <h3 style={{ marginBottom: '0.75rem' }}>Resources</h3>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <ResourceButton icon="📘" label="User Guide" onClick={() => setGuideOpen((o) => !o)} />
          <ResourceButton icon="📄" label="Technical Documentation" disabled disabledHint="Not published yet" />
          <ResourceButton
            icon="📥"
            label={downloadSampleMutation.isPending ? 'Preparing…' : 'Sample Configuration'}
            onClick={() => downloadSampleMutation.mutate()}
          />
          <ResourceButton icon="❓" label="FAQ" onClick={() => setFaqOpen((o) => !o)} />
        </div>
        {downloadSampleMutation.isError && (
          <div style={{ marginTop: '0.75rem' }}>
            <Callout variant="error">Could not prepare the sample configuration download.</Callout>
          </div>
        )}

        {guideOpen && (
          <div className="card" style={{ padding: '1.25rem', marginTop: '1rem' }}>
            <div style={{ fontWeight: 700, marginBottom: '0.75rem' }}>📘 What-If Setup — at a glance</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {GUIDE_SECTIONS.map((section) => (
                <div key={section.title}>
                  <div className="caption" style={{ fontWeight: 700, marginBottom: '0.3rem' }}>{section.title}</div>
                  <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                    {section.items.map((item) => (
                      <li key={item} className="caption">{item}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        )}

        {faqOpen && (
          <div className="card" style={{ padding: '1.25rem', marginTop: '1rem' }}>
            <div style={{ fontWeight: 700, marginBottom: '0.6rem' }}>❓ Frequently Asked Questions</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {FAQ_ITEMS.map((item) => (
                <p key={item.q} className="caption" style={{ margin: 0 }}>
                  <strong>{item.q}</strong> {item.a}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
