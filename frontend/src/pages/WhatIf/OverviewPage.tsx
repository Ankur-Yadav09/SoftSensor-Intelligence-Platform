import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
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
  saveConfig,
} from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { StatusCard } from '../../components/StatusCard'
import { useActiveWhatIf } from '../../state/ActiveWhatIfContext'

// "Start New Case" clears the one shared Config_file.xlsx back to blank —
// this app has no per-case storage (ARCHITECTURE.md's file-based What-If
// persistence model), so "new" can only mean "reset the shared file," never
// "create an isolated blank copy." Scoped to the 8 config sheets only —
// trained Kalman .pkl artifacts and Soft Sensor saved_models/Experiment
// History selections are a separate persistence world and are untouched.
const EMPTY_CONFIG_PAYLOAD = {
  pi_mapping_rows: [],
  model_details_rows: [],
  constraints_rows: [],
  user_inputs_rows: [],
  display_order_rows: [],
  section_order_rows: [],
  mvdvcv_rows: [],
  target_section: null,
}

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
      'Model Development — Connect Data, Data Health, Model Definition, AI Feature Discovery, Build Model. Freely revisit any step, rebuild, and run as many experiments as you need.',
      'Experimentation & Model Selection — compare every experiment for a Predicted Parameter and mark one "Selected for What-If Analysis". What-If Analysis then uses it automatically; parameters with no selection fall back to the dedicated Kalman model (trained from the "Advanced" section there).',
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
    a: 'Go to What-If Setup — it unlocks once PI Tag Mapping, Model Mapping, and every predicted parameter has a model (either a trained Kalman model, or an experiment marked "Selected for What-If Analysis" in Experimentation & Model Selection).',
  },
  {
    q: 'Which model does What-If Analysis actually use for a parameter?',
    a: 'Whichever experiment you marked "Selected for What-If Analysis" for that parameter, in Model Config → Experimentation & Model Selection. If none is selected, it falls back to that parameter\'s dedicated Kalman model.',
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
  const queryClient = useQueryClient()
  const { targetSection, setTargetSection, setGeneratedTags } = useActiveWhatIf()
  const [guideOpen, setGuideOpen] = useState(false)
  const [faqOpen, setFaqOpen] = useState(false)
  const guideRef = useRef<HTMLDivElement>(null)
  const faqRef = useRef<HTMLDivElement>(null)

  // Opening the User Guide / FAQ reveals a panel below the Resources
  // buttons — on a shorter viewport that panel lands off-screen, so
  // scroll it into view instead of leaving the user to notice and scroll
  // down themselves.
  useEffect(() => {
    if (guideOpen) guideRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [guideOpen])
  useEffect(() => {
    if (faqOpen) faqRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [faqOpen])

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

  const resetCaseMutation = useMutation({
    mutationFn: () => saveConfig(EMPTY_CONFIG_PAYLOAD),
    onSuccess: () => {
      for (const key of [
        'whatif-config-status',
        'whatif-models-status',
        'whatif-pi-mapping',
        'whatif-model-mapping',
        'whatif-section-order',
        'whatif-mvdvcv',
        'whatif-constraints',
        'whatif-user-inputs',
        'whatif-column-order',
        'whatif-target-section',
        'whatif-detected-counts',
      ]) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
      setTargetSection(null)
      setGeneratedTags([])
      navigate('/what-if/case-setup')
    },
  })

  function startNewCase() {
    const confirmed = window.confirm(
      'This clears the current configuration (PI Tag Mapping, Model Mapping, Constraints, User Inputs, ' +
        'Results Layout, Section Order, MV/DV/CV Tag List, Target Section) for everyone using this app — ' +
        'there is only one shared configuration file. Trained models and Experiment History selections are ' +
        'not affected. Continue?',
    )
    if (confirmed) resetCaseMutation.mutate()
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
          <button onClick={startNewCase} disabled={resetCaseMutation.isPending}>
            {resetCaseMutation.isPending ? 'Clearing…' : '▶ Start New Case'}
          </button>
          <button
            className="chip"
            onClick={resumeCase}
            disabled={!hasAnyConfig}
            title={hasAnyConfig ? undefined : 'No existing configuration found yet'}
          >
            ⏩ Resume Existing Case
          </button>
        </div>
        {resetCaseMutation.isError && (
          <Callout variant="error">Could not clear the configuration. Please try again.</Callout>
        )}
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
          <div ref={guideRef} className="card" style={{ padding: '1.25rem', marginTop: '1rem' }}>
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
          <div ref={faqRef} className="card" style={{ padding: '1.25rem', marginTop: '1rem' }}>
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
