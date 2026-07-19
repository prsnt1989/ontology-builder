import { Check, Loader2 } from 'lucide-react'
import { cn } from '../lib/utils'

export const PIPELINE_PHASES = [
  { key: 'intake', label: 'Intake' },
  { key: 'research', label: 'Research' },
  { key: 'design', label: 'Design' },
  { key: 'actions_rules', label: 'Actions & Rules' },
  { key: 'validation', label: 'Validation' },
  { key: 'generating', label: 'Generate' },
  { key: 'qa', label: 'Ready' },
] as const

// Update flow: change-request intake → design patch → actions/rules → validation → generate → ready.
export const UPDATE_PHASES = [
  { key: 'update_intake', label: 'Change Request' },
  { key: 'update_research', label: 'Research' },
  { key: 'update_design', label: 'Design' },
  { key: 'update_actions_rules', label: 'Actions & Rules' },
  { key: 'update_validation', label: 'Validation' },
  { key: 'update_generating', label: 'Generate' },
  { key: 'qa', label: 'Ready' },
] as const

interface Props {
  phase: string
  loading: boolean
  block?: number
  totalBlocks?: number
  variant?: 'build' | 'update'
}

export function PhaseTimeline({ phase, loading, block, totalBlocks, variant = 'build' }: Props) {
  const phases = variant === 'update' ? UPDATE_PHASES : PIPELINE_PHASES
  // update_research has no dedicated executor; treat it as the design step for the timeline.
  const normalizedPhase = phase === 'update_research' ? 'update_design' : phase
  const activeIdx = (() => {
    const i = phases.findIndex((p) => p.key === normalizedPhase)
    return i === -1 ? 0 : i
  })()
  const isIntake = phase === 'intake' || phase === 'update_intake'

  return (
    <div className="flex items-center gap-1 overflow-x-auto px-6 py-3">
      {phases.map((p, idx) => {
        const done = idx < activeIdx
        const active = idx === activeIdx
        const isLast = idx === phases.length - 1

        return (
          <div key={p.key} className="flex shrink-0 items-center">
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  'flex size-6 items-center justify-center rounded-full text-xs font-semibold transition-colors',
                  done && 'bg-chart-2 text-white',
                  active && 'bg-primary text-primary-foreground',
                  !done && !active && 'bg-muted text-muted-foreground'
                )}
              >
                {done ? (
                  <Check className="size-3.5" />
                ) : active && loading ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  idx + 1
                )}
              </div>
              <span
                className={cn(
                  'text-xs font-medium whitespace-nowrap',
                  active ? 'text-foreground' : 'text-muted-foreground'
                )}
              >
                {p.label}
                {active && isIntake && block && totalBlocks ? (
                  <span className="ml-1 text-muted-foreground">
                    {block}/{totalBlocks}
                  </span>
                ) : null}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  'mx-2 h-px w-6 transition-colors',
                  done ? 'bg-chart-2' : 'bg-border'
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
