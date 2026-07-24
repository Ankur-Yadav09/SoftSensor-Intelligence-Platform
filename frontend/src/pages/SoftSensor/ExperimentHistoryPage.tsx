import { useQuery } from '@tanstack/react-query'
import { getOverview } from '../../api/overview'
import { Callout } from '../../components/Callout'
import type { SavedModelSummary } from '../../api/types'

function fmt(value: number | null): string {
  return value != null ? value.toFixed(4) : '—'
}

// Comma-joined column lists can run long (30+ features on this dataset) —
// clip visually with an ellipsis but keep the full list one hover away via
// the native title tooltip, rather than build a new expand/collapse widget.
function ColumnList({ cols }: { cols: string[] }) {
  const text = cols.join(', ') || '—'
  return (
    <span
      title={text}
      style={{
        display: 'inline-block',
        maxWidth: 280,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        verticalAlign: 'bottom',
      }}
    >
      {text}
    </span>
  )
}

// A plain, business-readable "one row per trained model" table — the
// domain-person-facing counterpart to MLflow's run list, built entirely
// from what training_service.py::_finish() already writes to the
// model_registry (no new tracking, just a new read-only view of it).
export function ExperimentHistoryPage() {
  const overviewQuery = useQuery({ queryKey: ['overview'], queryFn: getOverview })

  if (overviewQuery.isLoading) return <p className="caption">Loading experiment history…</p>
  if (overviewQuery.isError) return <p className="caption">Failed to load experiment history.</p>

  const models: SavedModelSummary[] = [...(overviewQuery.data?.saved_models ?? [])].sort((a, b) =>
    a.saved_at < b.saved_at ? 1 : -1,
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div>
        <h1>📋 Experiment History</h1>
        <p className="caption">
          Every trained model, one row each — dataset used, target/input features, and train vs. test accuracy.
        </p>
      </div>

      {models.length === 0 ? (
        <Callout variant="info">Train a model to see its experiment history here.</Callout>
      ) : (
        <div className="card" style={{ padding: '1.5rem' }}>
          <div className="data-table-scroll" style={{ overflowX: 'auto', maxHeight: 560, overflowY: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Algorithm</th>
                  <th>Trained At</th>
                  <th>Dataset</th>
                  <th>Target (Y)</th>
                  <th>Input Features (X)</th>
                  <th>Train R²</th>
                  <th>Train MAE</th>
                  <th>Test R²</th>
                  <th>Test MAE</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.name}>
                    <td>
                      <code>{m.name}</code>
                    </td>
                    <td>{m.algorithm ?? '—'}</td>
                    <td>{m.saved_at}</td>
                    <td>{m.dataset_name ?? '—'}</td>
                    <td>
                      <ColumnList cols={m.y_cols} />
                    </td>
                    <td>
                      <ColumnList cols={m.x_cols} />
                    </td>
                    <td>{fmt(m.train_r2)}</td>
                    <td>{fmt(m.train_mae)}</td>
                    <td>{fmt(m.avg_r2)}</td>
                    <td>{fmt(m.avg_mae)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
