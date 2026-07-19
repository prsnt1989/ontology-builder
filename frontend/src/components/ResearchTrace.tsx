import { Search, Lightbulb, Boxes, Globe } from 'lucide-react'
import type { ResearchTrace as ResearchTrace_ } from '../lib/agui'
import { Badge } from './ui/badge'

function labelOf(item: unknown): string {
  if (typeof item === 'string') return item
  if (item && typeof item === 'object') {
    const o = item as Record<string, unknown>
    return String(
      o.display_name ?? o.name ?? o.api_name ?? o.title ?? o.pattern_name ?? o.pattern ?? ''
    )
  }
  return String(item)
}

function descOf(item: unknown): string | null {
  if (item && typeof item === 'object') {
    const o = item as Record<string, unknown>
    const d = o.description ?? o.desc ?? o.detail
    return typeof d === 'string' ? d : null
  }
  return null
}

export function ResearchTrace({ trace }: { trace: ResearchTrace_ }) {
  const objectTypes = trace.recommended_object_types ?? []
  const patterns = trace.industry_patterns ?? []
  const practices = trace.best_practices ?? []
  const sources = trace.sources ?? []

  return (
    <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <Search className="size-4 text-primary" />
        Research Trace
      </div>

      <div className="space-y-3 text-sm">
        {(trace.industry || trace.domain) && (
          <div className="flex flex-wrap gap-2">
            {trace.industry && <Badge variant="info">{trace.industry}</Badge>}
            {trace.domain && <Badge variant="secondary">{trace.domain}</Badge>}
          </div>
        )}

        {objectTypes.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <Boxes className="size-3.5" />
              Recommended object types ({objectTypes.length})
            </div>
            <div className="flex flex-wrap gap-1">
              {objectTypes.slice(0, 12).map((t, i) => (
                <span
                  key={i}
                  className="rounded-md border border-border bg-background px-1.5 py-0.5 text-xs"
                >
                  {labelOf(t)}
                </span>
              ))}
            </div>
          </div>
        )}

        {patterns.length > 0 && (
          <div>
            <div className="mb-1 text-xs font-semibold text-muted-foreground">Industry patterns</div>
            <ul className="space-y-1">
              {patterns.slice(0, 5).map((p, i) => {
                const label = labelOf(p)
                const desc = descOf(p)
                return (
                  <li key={i} className="flex gap-2 text-xs text-foreground/80">
                    <span className="text-primary">•</span>
                    <span>
                      {label && <span className="font-medium">{label}</span>}
                      {label && desc ? ': ' : ''}
                      {desc && <span className="text-muted-foreground">{desc}</span>}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        {practices.length > 0 && (
          <div>
            <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <Lightbulb className="size-3.5" />
              Best practices
            </div>
            <ul className="space-y-0.5">
              {practices.slice(0, 5).map((p, i) => (
                <li key={i} className="flex gap-2 text-xs text-foreground/80">
                  <span className="text-primary">•</span>
                  <span>{labelOf(p)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {sources.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Globe className="size-3.5" />
            {sources.length} sources consulted
          </div>
        )}
      </div>
    </div>
  )
}
