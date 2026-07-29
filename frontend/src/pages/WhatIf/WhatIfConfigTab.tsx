import { useQuery } from '@tanstack/react-query'
import { getColumnOrder, getConstraints, getPiMapping, getSectionOrder, getUserInputs } from '../../api/whatIf'
import { Tabs } from '../../components/Tabs'
import { useActiveWhatIf } from '../../state/ActiveWhatIfContext'
import { allowedSet, scopedTagOptions } from './caseSetupHelpers'
import { ColumnOrderEditor } from './ColumnOrderEditor'
import { ConstraintsEditor } from './ConstraintsEditor'
import { UserInputsEditor } from './UserInputsEditor'

// "What-If Config" section of What-If Setup — the optional pieces
// (Constraints, User Inputs, Results Layout), unchanged from before, just
// reorganized as horizontal sub-tabs instead of vertical wizard steps.
export function WhatIfConfigTab() {
  const { targetSection } = useActiveWhatIf()
  const sectionOrderQuery = useQuery({ queryKey: ['whatif-section-order'], queryFn: getSectionOrder })
  const piMappingQuery = useQuery({ queryKey: ['whatif-pi-mapping'], queryFn: getPiMapping })
  const constraintsQuery = useQuery({ queryKey: ['whatif-constraints'], queryFn: getConstraints })
  const userInputsQuery = useQuery({ queryKey: ['whatif-user-inputs'], queryFn: getUserInputs })
  const columnOrderQuery = useQuery({ queryKey: ['whatif-column-order'], queryFn: getColumnOrder })

  const sectionOrderList = (sectionOrderQuery.data ?? []).map((r) => r.Section?.trim() ?? '').filter(Boolean)
  const allowed = allowedSet(sectionOrderList, targetSection)
  const tagOptions = scopedTagOptions(piMappingQuery.data ?? [], allowed)

  return (
    <Tabs
      tabs={[
        {
          label: 'Constraints',
          complete: (constraintsQuery.data ?? []).length > 0,
          content: (
            <div>
              <p className="caption">
                Optional. Operating limits and the generic bump/abort rules that drive constraint checks during a
                what-if run.
              </p>
              <ConstraintsEditor tagOptions={tagOptions} />
            </div>
          ),
        },
        {
          label: 'User Inputs',
          complete: (userInputsQuery.data ?? []).length > 0,
          content: (
            <div>
              <p className="caption">Optional. Parameters the operator can override, with their allowed range.</p>
              <UserInputsEditor tagOptions={tagOptions} />
            </div>
          ),
        },
        {
          label: 'Results Layout',
          complete: (columnOrderQuery.data ?? []).length > 0,
          content: (
            <div>
              <p className="caption">
                Optional. Preferred column display order for the Actual-vs-Estimated results table and CSV exports.
              </p>
              <ColumnOrderEditor tagOptions={tagOptions} />
            </div>
          ),
        },
      ]}
    />
  )
}
