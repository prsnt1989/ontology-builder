import { useState } from 'react'
import { GitPullRequestArrow, Plus, X, Check, ArrowLeft, Trash2 } from 'lucide-react'
import { Button } from './ui/button'
import { Input } from './ui/input'

interface Props {
  onSubmit: (changes: string[]) => void
  onClose: () => void
}

/**
 * Collect a batch of ontology change requests, review/edit them, then submit.
 * The batch is handed to the caller (App) which starts the Update Ontology flow.
 */
export function RequestChangesModal({ onSubmit, onClose }: Props) {
  const [phase, setPhase] = useState<'collect' | 'approve'>('collect')
  const [rows, setRows] = useState<string[]>([])
  const [draft, setDraft] = useState('')

  const addRow = () => {
    const t = draft.trim()
    if (!t) return
    setRows((r) => [...r, t])
    setDraft('')
  }

  const removeRow = (i: number) => setRows((r) => r.filter((_, idx) => idx !== i))
  const editRow = (i: number, value: string) =>
    setRows((r) => r.map((row, idx) => (idx === i ? value : row)))

  const cleanRows = rows.map((r) => r.trim()).filter(Boolean)

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center">
      <div className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-xl bg-card shadow-xl ring-1 ring-foreground/10 animate-in slide-in-from-bottom-4">
        {/* Header */}
        <div className="flex items-start gap-3 border-b border-border p-5">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
            <GitPullRequestArrow className="size-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-semibold">
              {phase === 'collect' ? 'Request changes' : 'Review changes'}
            </h3>
            <p className="text-sm text-muted-foreground">
              {phase === 'collect'
                ? 'Add each change you want to make. They’ll be collected here first.'
                : `These ${cleanRows.length} change${cleanRows.length === 1 ? '' : 's'} will go to the update assistant, which asks a few follow-up questions before anything is applied.`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {phase === 'collect' ? (
            <>
              <div className="flex items-center gap-2">
                <Input
                  autoFocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addRow()
                    }
                  }}
                  placeholder="e.g. Add a priority field to Incident"
                />
                <Button onClick={addRow} disabled={!draft.trim()} size="sm">
                  <Plus className="size-4" />
                  Add
                </Button>
              </div>

              <div className="mt-4 space-y-2">
                {rows.length === 0 && (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    No changes added yet.
                  </p>
                )}
                {rows.map((row, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2"
                  >
                    <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1 text-sm">{row}</span>
                    <button
                      onClick={() => removeRow(i)}
                      className="shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                      aria-label="Remove"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="space-y-2">
              {rows.map((row, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                    {i + 1}
                  </span>
                  <Input value={row} onChange={(e) => editRow(i, e.target.value)} />
                  <button
                    onClick={() => removeRow(i)}
                    className="shrink-0 rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                    aria-label="Remove"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              ))}
              <button
                onClick={() => setPhase('collect')}
                className="flex items-center gap-1 pt-1 text-xs font-medium text-primary hover:underline"
              >
                <Plus className="size-3.5" />
                Add another change
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 border-t border-border bg-muted/50 p-4">
          {phase === 'collect' ? (
            <>
              <Button variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={() => setPhase('approve')} disabled={cleanRows.length === 0}>
                Publish changes
                <span className="ml-0.5 rounded bg-primary-foreground/20 px-1.5 text-xs">
                  {cleanRows.length}
                </span>
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setPhase('collect')}>
                <ArrowLeft className="size-4" />
                Back
              </Button>
              <Button onClick={() => onSubmit(cleanRows)} disabled={cleanRows.length === 0}>
                <Check className="size-4" />
                Approve &amp; start
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
