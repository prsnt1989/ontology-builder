import { Loader2, CheckCircle2, XCircle, Activity } from 'lucide-react'
import type { AgentActivity as Activity_ } from '../lib/agui'
import { cn } from '../lib/utils'

export interface ActivityEntry extends Activity_ {
  id: string
}

const PHASE_LABELS: Record<string, string> = {
  research: 'Research',
  design: 'Design',
  actions_rules: 'Actions & Rules',
  validation: 'Validation',
  generating: 'Generation',
}

const AGENT_LABELS: Record<string, string> = {
  research: 'Domain researcher',
  design: 'Ontology designer',
  actions_rules: 'Actions & rules designer',
  validation: 'Validator',
  yaml_writer: 'YAML writer',
  datastore: 'Database provisioner',
}

export function AgentActivity({ entries }: { entries: ActivityEntry[] }) {
  if (entries.length === 0) return null

  return (
    <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <Activity className="size-4 text-primary" />
        Agent Activity
      </div>
      <div className="space-y-2">
        {entries.map((e) => (
          <div key={e.id} className="flex items-start gap-2.5 text-sm">
            <div className="mt-0.5 shrink-0">
              {e.status === 'running' ? (
                <Loader2 className="size-4 animate-spin text-primary" />
              ) : e.status === 'failed' ? (
                <XCircle className="size-4 text-destructive" />
              ) : (
                <CheckCircle2 className="size-4 text-chart-2" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{AGENT_LABELS[e.agent] || e.agent}</span>
                <span className="text-xs text-muted-foreground">
                  {PHASE_LABELS[e.phase] || e.phase}
                </span>
              </div>
              {e.detail && (
                <div
                  className={cn(
                    'text-xs',
                    e.status === 'failed' ? 'text-destructive' : 'text-muted-foreground'
                  )}
                >
                  {e.detail}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
