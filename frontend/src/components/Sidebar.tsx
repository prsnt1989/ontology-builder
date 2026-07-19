import { useState } from 'react'
import {
  Boxes,
  MessageSquare,
  FlaskConical,
  FileCode2,
  Database,
  Plus,
  ChevronDown,
  Circle,
  CheckCircle2,
  Trash2,
} from 'lucide-react'
import type { AppMode } from '../lib/types'
import type { SessionInfo } from '../lib/api'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { cn } from '../lib/utils'

interface NavItem {
  mode: AppMode
  label: string
  icon: typeof MessageSquare
  requiresOntology: boolean
}

const NAV_ITEMS: NavItem[] = [
  { mode: 'build', label: 'Build', icon: MessageSquare, requiresOntology: false },
  { mode: 'ontology', label: 'Ontology', icon: FileCode2, requiresOntology: true },
  { mode: 'qa', label: 'Test Q&A', icon: FlaskConical, requiresOntology: true },
  { mode: 'data', label: 'Data Explorer', icon: Database, requiresOntology: true },
]

interface Props {
  mode: AppMode
  onModeChange: (mode: AppMode) => void
  ontologyReady: boolean
  sessions: SessionInfo[]
  currentSessionId: string | null
  currentCompany: string | null
  onSelectSession: (session: SessionInfo) => void
  onNewSession: () => void
  onDeleteSession: (sessionId: string) => void
  onRefreshSessions: () => void
  skillsSlot?: React.ReactNode
}

export function Sidebar({
  mode,
  onModeChange,
  ontologyReady,
  sessions,
  currentSessionId,
  currentCompany,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onRefreshSessions,
  skillsSlot,
}: Props) {
  const [pickerOpen, setPickerOpen] = useState(false)

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-border bg-sidebar">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Boxes className="size-5" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold leading-tight text-sidebar-foreground">
            Ontology Builder
          </div>
          <div className="truncate text-xs text-muted-foreground">Foundry-style designer</div>
        </div>
      </div>

      {/* Session picker */}
      <div className="relative px-3 pb-2">
        <button
          onClick={() => {
            onRefreshSessions()
            setPickerOpen((v) => !v)
          }}
          className="flex w-full items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
        >
          {ontologyReady ? (
            <CheckCircle2 className="size-4 shrink-0 text-chart-2" />
          ) : (
            <Circle className="size-4 shrink-0 text-chart-3" />
          )}
          <span className="min-w-0 flex-1 truncate">
            {currentCompany || 'Current session'}
          </span>
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        </button>

        {pickerOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setPickerOpen(false)} />
            <div className="absolute left-3 right-3 z-50 mt-1 overflow-hidden rounded-lg border border-border bg-popover shadow-lg">
              <div className="border-b border-border p-1.5">
                <button
                  onClick={() => {
                    onNewSession()
                    setPickerOpen(false)
                  }}
                  className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm font-medium text-primary transition-colors hover:bg-muted"
                >
                  <Plus className="size-4" />
                  New session
                </button>
              </div>
              <div className="max-h-72 overflow-y-auto p-1.5">
                {sessions.length === 0 && (
                  <div className="px-2.5 py-6 text-center text-sm text-muted-foreground">
                    No sessions yet
                  </div>
                )}
                {sessions.map((s) => (
                  <div
                    key={s.session_id}
                    className={cn(
                      'group flex items-center gap-2 rounded-md px-2.5 py-2 transition-colors hover:bg-muted',
                      s.session_id === currentSessionId && 'bg-muted'
                    )}
                  >
                    <button
                      onClick={() => {
                        onSelectSession(s)
                        setPickerOpen(false)
                      }}
                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                    >
                      {s.ontology_ready ? (
                        <CheckCircle2 className="size-3.5 shrink-0 text-chart-2" />
                      ) : (
                        <Circle className="size-3.5 shrink-0 text-chart-3" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm">{s.company || 'Unnamed'}</div>
                        <div className="truncate text-xs text-muted-foreground">{s.phase}</div>
                      </div>
                    </button>
                    <button
                      onClick={() => onDeleteSession(s.session_id)}
                      className="shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                      aria-label="Delete session"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 px-3 py-2">
        <div className="px-2.5 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Workspace
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const disabled = item.requiresOntology && !ontologyReady
          const active = mode === item.mode
          return (
            <button
              key={item.mode}
              onClick={() => !disabled && onModeChange(item.mode)}
              disabled={disabled}
              className={cn(
                'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors',
                active
                  ? 'bg-accent text-accent-foreground'
                  : 'text-sidebar-foreground/80 hover:bg-muted hover:text-sidebar-foreground',
                disabled && 'cursor-not-allowed opacity-40 hover:bg-transparent'
              )}
            >
              <Icon className="size-4 shrink-0" />
              <span className="flex-1 text-left">{item.label}</span>
              {disabled && (
                <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
                  locked
                </Badge>
              )}
            </button>
          )
        })}
      </nav>

      {/* Skills panel slot */}
      {skillsSlot && <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">{skillsSlot}</div>}
      {!skillsSlot && <div className="flex-1" />}

      {/* Footer */}
      <div className="border-t border-border px-4 py-3">
        <Button variant="outline" size="sm" className="w-full" onClick={onNewSession}>
          <Plus className="size-4" />
          New ontology
        </Button>
      </div>
    </aside>
  )
}
