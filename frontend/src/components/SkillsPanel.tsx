import { useEffect, useState } from 'react'
import { Puzzle, Zap } from 'lucide-react'
import { listSkills, type SkillInfo } from '../lib/api'
import { cn } from '../lib/utils'

interface Props {
  activePhase: string
}

export function SkillsPanel({ activePhase }: Props) {
  const [skills, setSkills] = useState<SkillInfo[]>([])

  useEffect(() => {
    listSkills()
      .then((r) => setSkills(r.skills))
      .catch(() => {})
  }, [])

  if (skills.length === 0) return null

  // A skill is active if the current phase (or its build-equivalent, e.g.
  // `update_design` → `design`) is among the skill's phases.
  const normalized = activePhase.replace(/^update_/, '')
  const isActive = (s: SkillInfo) => {
    const phases = s.phases && s.phases.length > 0 ? s.phases : s.phase ? [s.phase] : []
    return phases.includes(activePhase) || phases.includes(normalized)
  }

  return (
    <div>
      <div className="flex items-center gap-1.5 px-2.5 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Puzzle className="size-3.5" />
        Agent Skills
      </div>
      <div className="space-y-1">
        {skills.map((s) => {
          const active = isActive(s)
          return (
            <div
              key={s.name}
              title={s.description}
              className={cn(
                'rounded-lg border px-2.5 py-2 transition-colors',
                active ? 'border-primary/40 bg-accent' : 'border-transparent'
              )}
            >
              <div className="flex items-center gap-1.5">
                {active && <Zap className="size-3 shrink-0 text-primary" />}
                <span
                  className={cn(
                    'truncate font-mono text-xs',
                    active ? 'font-medium text-accent-foreground' : 'text-sidebar-foreground/70'
                  )}
                >
                  {s.name}
                </span>
              </div>
              <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-muted-foreground">
                {s.description}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
