import { useQuery } from '@tanstack/react-query'
import { getPiMapping } from '../../api/whatIf'
import { DataTable } from '../../components/DataTable'

export function PiTagMappingEditor() {
  const query = useQuery({ queryKey: ['whatif-pi-mapping'], queryFn: getPiMapping })

  return (
    <div>
      <p className="caption">
        Master PI dictionary (Pi_tags → Generalized Description → Section). Blank sections are auto-clubbed from tag
        names.
      </p>
      <DataTable
        columns={[
          { header: 'Pi_tags', render: (r) => r.Pi_tags },
          { header: 'Generalized Description', render: (r) => r['Generalized Description'] },
          { header: 'Section', render: (r) => r.Section },
        ]}
        rows={query.data ?? []}
        keyFn={(r) => r.Pi_tags}
        maxVisibleRows={10}
        emptyMessage="No PI tag dictionary loaded."
      />
    </div>
  )
}
