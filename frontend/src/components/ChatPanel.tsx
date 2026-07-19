import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  Send,
  Boxes,
  FlaskConical,
  GitPullRequestArrow,
  AlertTriangle,
  XCircle,
  Sparkles,
  ArrowRight,
} from 'lucide-react'
import type { Message, AppMode, SpecialistData } from '../lib/types'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { cn } from '../lib/utils'

// 'update' is a display variant used inside the Ontology workspace's Update tab
// (it is no longer a top-level AppMode/route).
export type ChatPanelMode = AppMode | 'update'

interface Props {
  messages: Message[]
  onSend: (text: string) => void
  loading: boolean
  mode: ChatPanelMode
}

const PHASE_LABELS: Record<string, string> = {
  intake: 'Questionnaire',
  research: 'Domain Research',
  design: 'Ontology Design',
  actions_rules: 'Actions & Rules',
  validation: 'Validation',
  generating: 'Generating Output',
  qa: 'Ready',
}

export function ChatPanel({ messages, onSend, loading, mode }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    onSend(input.trim())
    setInput('')
  }

  const getPrevPhase = (index: number): string | undefined => {
    for (let i = index - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant' && messages[i].phase) {
        return messages[i].phase
      }
    }
    return undefined
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-6 py-6">
          {messages.length === 0 && (
            <div className="mx-auto mt-16 max-w-md text-center">
              <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                {mode === 'qa' ? (
                  <FlaskConical className="size-6" />
                ) : mode === 'update' ? (
                  <GitPullRequestArrow className="size-6" />
                ) : (
                  <Boxes className="size-6" />
                )}
              </div>
              <h2 className="mb-2 text-xl font-semibold text-foreground">
                {mode === 'qa'
                  ? 'Test Your Ontology'
                  : mode === 'update'
                    ? 'Update Your Ontology'
                    : 'Design Your Ontology'}
              </h2>
              <p className="text-sm text-muted-foreground">
                {mode === 'qa'
                  ? 'Ask questions about your data in plain English to validate the ontology works correctly.'
                  : mode === 'update'
                    ? "Describe a change you'd like to make — add a field, a new object type, a relationship, and so on. I'll ask a few tailored questions per change. Keep adding changes, then say “done” to review and apply them all."
                    : "I'll guide you through 7 sections — Company Profile, Business Domain, Problem Statement, Data Sources, Users & Permissions, Workflows, and Constraints. Tell me about your company to begin."}
              </p>
            </div>
          )}

          <div className="space-y-5">
            {messages.map((msg, idx) => {
              const prevPhase = getPrevPhase(idx)
              const showPhaseTransition =
                msg.role === 'assistant' && msg.phase && prevPhase && msg.phase !== prevPhase

              return (
                <div key={msg.id}>
                  {showPhaseTransition && (
                    <div className="my-4 flex items-center justify-center">
                      <Badge variant="success" className="gap-1">
                        <ArrowRight className="size-3" />
                        {PHASE_LABELS[prevPhase!] || prevPhase} complete
                      </Badge>
                    </div>
                  )}

                  <div className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                    <div
                      className={cn(
                        'max-w-[85%] rounded-xl px-4 py-3 text-sm',
                        msg.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-card text-card-foreground ring-1 ring-foreground/10'
                      )}
                    >
                      <div
                        className={cn(
                          'prose prose-sm max-w-none prose-p:my-1.5 prose-headings:mt-2 prose-headings:mb-1 prose-ul:my-1.5 prose-li:my-0.5',
                          msg.role === 'user'
                            ? 'prose-invert prose-strong:text-primary-foreground'
                            : 'dark:prose-invert'
                        )}
                      >
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>

                      {msg.specialistData && (
                        <SpecialistDisplay data={msg.specialistData} onSend={onSend} />
                      )}
                    </div>
                  </div>
                </div>
              )
            })}

            {loading && (
              <div className="flex justify-start">
                <div className="rounded-xl bg-card px-4 py-3 ring-1 ring-foreground/10">
                  <div className="flex gap-1">
                    <div className="size-2 animate-bounce rounded-full bg-muted-foreground/60" />
                    <div className="size-2 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:0.15s]" />
                    <div className="size-2 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:0.3s]" />
                  </div>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-border bg-background">
        <form onSubmit={handleSubmit} className="mx-auto max-w-3xl px-6 py-4">
          <div className="flex items-end gap-2 rounded-xl border border-input bg-card p-2 ring-1 ring-foreground/5 transition-colors focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e)
                }
              }}
              rows={1}
              placeholder={
                mode === 'qa'
                  ? 'Ask a question about your data…'
                  : mode === 'update'
                    ? 'Describe a change (or say “done” to review)…'
                    : 'Type your response…'
              }
              className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
              disabled={loading}
            />
            <Button type="submit" size="icon" disabled={loading || !input.trim()}>
              <Send className="size-4" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

function SpecialistDisplay({
  data,
  onSend,
}: {
  data: SpecialistData
  onSend: (text: string) => void
}) {
  return (
    <div className="mt-3 space-y-3">
      {data.sql && (
        <div className="overflow-hidden rounded-lg border border-border bg-muted/40">
          <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
            <span className="text-xs font-medium text-muted-foreground">Generated SQL</span>
            {data.row_count !== undefined && (
              <span className="text-xs text-muted-foreground">{data.row_count} rows</span>
            )}
          </div>
          <pre className="overflow-x-auto px-3 py-2 font-mono text-xs text-chart-2">{data.sql}</pre>
        </div>
      )}

      {data.summary_table && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="bg-muted/50">
                {data.summary_table.headers.map((h, i) => (
                  <th
                    key={i}
                    className="border-b border-border px-3 py-2 text-left font-semibold text-foreground"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.summary_table.rows.slice(0, 10).map((row, i) => (
                <tr key={i} className="hover:bg-muted/40">
                  {row.map((cell, j) => (
                    <td key={j} className="border-b border-border px-3 py-1.5 text-muted-foreground">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.insights && data.insights.length > 0 && (
        <div className="rounded-lg border border-border bg-accent/40 p-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-accent-foreground">
            <Sparkles className="size-3.5" />
            Key Insights
          </div>
          <ul className="space-y-1">
            {data.insights.map((insight, i) => (
              <li key={i} className="flex gap-2 text-xs text-foreground/80">
                <span className="text-primary">•</span>
                <span>{insight}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.issues && data.issues.length > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
            Validation Issues
            {data.overall_score !== undefined && (
              <Badge variant={data.overall_score >= 80 ? 'success' : 'warning'}>
                Score {data.overall_score}/100
              </Badge>
            )}
          </div>
          {data.issues
            .filter((i) => i.severity === 'critical')
            .map((issue, idx) => (
              <div
                key={`c-${idx}`}
                className="flex gap-2 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive"
              >
                <XCircle className="size-3.5 shrink-0" />
                <span>
                  {issue.message}
                  {issue.suggestion ? ` — ${issue.suggestion}` : ''}
                </span>
              </div>
            ))}
          {data.issues
            .filter((i) => i.severity === 'warning')
            .map((issue, idx) => (
              <div
                key={`w-${idx}`}
                className="flex gap-2 rounded-md bg-chart-3/10 px-2.5 py-1.5 text-xs text-chart-3"
              >
                <AlertTriangle className="size-3.5 shrink-0" />
                <span>
                  {issue.message}
                  {issue.suggestion ? ` — ${issue.suggestion}` : ''}
                </span>
              </div>
            ))}
        </div>
      )}

      {data.kind !== 'gathering' && data.follow_up_questions && data.follow_up_questions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.follow_up_questions.map((q, i) => (
            <button
              key={i}
              onClick={() => onSend(q)}
              className="rounded-full border border-border bg-background px-2.5 py-1 text-xs font-medium text-foreground/80 transition-colors hover:border-primary/40 hover:bg-accent hover:text-accent-foreground"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
