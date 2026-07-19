import { useState, useEffect } from 'react'
import { Table2, Database } from 'lucide-react'
import { getTables, getTableData } from '../lib/api'
import type { TableInfo } from '../lib/api'
import { Badge } from './ui/badge'
import { cn } from '../lib/utils'

interface Props {
  sessionId: string
}

export function DataExplorer({ sessionId }: Props) {
  const [tables, setTables] = useState<TableInfo[]>([])
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [columns, setColumns] = useState<string[]>([])
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [totalRows, setTotalRows] = useState(0)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getTables(sessionId)
      .then((res) => setTables(res.tables))
      .catch(() => {})
  }, [sessionId])

  const loadTable = async (tableName: string) => {
    setLoading(true)
    setSelectedTable(tableName)
    try {
      const data = await getTableData(sessionId, tableName)
      setColumns(data.columns)
      setRows(data.rows)
      setTotalRows(data.total_rows)
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-64 shrink-0 overflow-y-auto border-r border-border bg-sidebar p-3">
        <h3 className="px-2 pb-2 pt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Tables
        </h3>
        <div className="space-y-0.5">
          {tables.map((t) => {
            const active = selectedTable === t.table_name
            return (
              <button
                key={t.table_name}
                onClick={() => loadTable(t.table_name)}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors',
                  active
                    ? 'bg-accent text-accent-foreground'
                    : 'text-sidebar-foreground/80 hover:bg-muted'
                )}
              >
                <Table2 className="size-4 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{t.table_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {t.column_count} cols · {t.row_count} rows
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-5">
        {!selectedTable && (
          <div className="mt-20 text-center text-sm text-muted-foreground">
            <Database className="mx-auto mb-3 size-8 opacity-40" />
            Select a table to view its data
          </div>
        )}

        {selectedTable && (
          <>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">{selectedTable}</h2>
              <Badge variant="secondary">{totalRows} rows</Badge>
            </div>

            {loading ? (
              <div className="text-sm text-muted-foreground">Loading…</div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="bg-muted/50">
                      {columns.map((col) => (
                        <th
                          key={col}
                          className="border-b border-border px-3 py-2 text-left font-semibold text-foreground"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={i} className="hover:bg-muted/40">
                        {columns.map((col) => (
                          <td
                            key={col}
                            className="border-b border-border px-3 py-2 text-muted-foreground"
                          >
                            {String(row[col] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
