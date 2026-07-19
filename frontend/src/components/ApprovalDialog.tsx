import { ShieldAlert, Check, X, Database } from 'lucide-react'
import type { PendingInterrupt } from '../lib/agui'
import { Button } from './ui/button'

interface Props {
  interrupt: PendingInterrupt
  busy: boolean
  onApprove: () => void
  onDeny: () => void
}

export function ApprovalDialog({ interrupt, busy, onApprove, onDeny }: Props) {
  const { title, detail, tables } = interrupt.data

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center">
      <div className="w-full max-w-lg animate-in slide-in-from-bottom-4 overflow-hidden rounded-xl bg-card shadow-xl ring-1 ring-foreground/10">
        <div className="flex items-start gap-3 border-b border-border p-5">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-chart-3/15 text-chart-3">
            <ShieldAlert className="size-5" />
          </div>
          <div className="min-w-0">
            <h3 className="text-base font-semibold">Approval required</h3>
            <p className="text-sm text-muted-foreground">{title}</p>
          </div>
        </div>

        <div className="space-y-4 p-5">
          <p className="text-sm text-foreground/80">{detail}</p>

          {tables && tables.length > 0 && (
            <div className="rounded-lg border border-border bg-muted/40 p-3">
              <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                <Database className="size-3.5" />
                {tables.length} tables to create
              </div>
              <div className="flex flex-wrap gap-1">
                {tables.filter(Boolean).map((t) => (
                  <span
                    key={t}
                    className="rounded-md border border-border bg-background px-1.5 py-0.5 font-mono text-xs"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border bg-muted/50 p-4">
          <Button variant="outline" onClick={onDeny} disabled={busy}>
            <X className="size-4" />
            Skip provisioning
          </Button>
          <Button onClick={onApprove} disabled={busy}>
            <Check className="size-4" />
            {busy ? 'Provisioning…' : 'Approve & provision'}
          </Button>
        </div>
      </div>
    </div>
  )
}
