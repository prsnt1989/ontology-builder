import { useState, useCallback, useEffect, useRef } from 'react'
import { Sun, Moon, Sparkles } from 'lucide-react'
import { ChatPanel } from './components/ChatPanel'
import { PhaseTimeline } from './components/PhaseTimeline'
import { DataExplorer } from './components/DataExplorer'
import { OntologyViewer, type ViewTab } from './components/OntologyViewer'
import { Sidebar } from './components/Sidebar'
import { AgentActivity, type ActivityEntry } from './components/AgentActivity'
import { ResearchTrace } from './components/ResearchTrace'
import { ApprovalDialog } from './components/ApprovalDialog'
import { SkillsPanel } from './components/SkillsPanel'
import { Badge } from './components/ui/badge'
import { sendMessage, askOntology, listSessions, deleteSession } from './lib/api'
import {
  startPipeline,
  startUpdatePipeline,
  resumeInterrupt,
  type PendingInterrupt,
  type ResearchTrace as ResearchTraceData,
  type PipelineHandlers,
} from './lib/agui'
import type { Message, AppMode } from './lib/types'
import type { SessionInfo } from './lib/api'
import { useTheme } from './lib/theme'

const MODE_TITLES: Record<AppMode, string> = {
  build: 'Build',
  qa: 'Test Q&A',
  ontology: 'Ontology',
  data: 'Data Explorer',
}

const PHASE_LABELS: Record<string, string> = {
  intake: 'Questionnaire',
  research: 'Domain Research',
  design: 'Ontology Design',
  actions_rules: 'Actions & Rules',
  validation: 'Validation',
  generating: 'Generating Output',
  qa: 'Ready',
  complete: 'Complete',
  update_intake: 'Change Request',
  update_research: 'Analyzing Changes',
  update_design: 'Applying Changes',
  update_actions_rules: 'Actions & Rules',
  update_validation: 'Validation',
  update_generating: 'Applying to Database',
}

// Maps the workflow executor id (STEP_STARTED name) → pipeline phase key (build + update).
const STEP_TO_PHASE: Record<string, string> = {
  research: 'research',
  design: 'design',
  actions_rules: 'actions_rules',
  validation: 'validation',
  generating: 'generating',
  update_design: 'update_design',
  update_actions_rules: 'update_actions_rules',
  update_validation: 'update_validation',
  update_generating: 'update_generating',
}

function App() {
  const { theme, toggleTheme } = useTheme()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [phase, setPhase] = useState('intake')
  const [progress, setProgress] = useState<{ block: number; total_blocks: number } | null>(null)
  const [mode, setMode] = useState<AppMode>('build')
  const [ontologyReady, setOntologyReady] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sessions, setSessions] = useState<SessionInfo[]>([])

  // Ontology workspace tabs (YAML · Graph · Update)
  const [ontologyTab, setOntologyTab] = useState<ViewTab>('yaml')
  const [showUpdateTab, setShowUpdateTab] = useState(false)

  // Live pipeline state
  const [activity, setActivity] = useState<ActivityEntry[]>([])
  const [researchTrace, setResearchTrace] = useState<ResearchTraceData | null>(null)
  const [pendingInterrupt, setPendingInterrupt] = useState<PendingInterrupt | null>(null)
  const [approvalBusy, setApprovalBusy] = useState(false)
  const pipelineStarted = useRef(false)
  const updatePipelineStarted = useRef(false)
  const isUpdateRun = useRef(false)
  const activityCounter = useRef(0)

  const refreshSessions = useCallback(() => {
    listSessions()
      .then(({ sessions: s }) => setSessions(s))
      .catch(() => {})
  }, [])

  useEffect(() => {
    listSessions()
      .then(({ sessions: s }) => {
        setSessions(s)
        if (s.length > 0) {
          const latest = s[0]
          setSessionId(latest.session_id)
          setPhase(latest.phase)
          if (latest.ontology_ready) {
            setOntologyReady(true)
            setMode('qa')
          }
          setMessages([
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: latest.ontology_ready
                ? `Session restored (${latest.company || 'Unknown'}). Your ontology is ready — ask questions or explore data.`
                : `Session restored (${latest.company || 'Unknown'}). Current phase: ${latest.phase}.`,
              timestamp: new Date(),
            },
          ])
        }
      })
      .catch(() => {})
  }, [])

  const resetPipelineState = () => {
    setActivity([])
    setResearchTrace(null)
    setPendingInterrupt(null)
    pipelineStarted.current = false
  }

  const selectSession = useCallback((session: SessionInfo) => {
    setSessionId(session.session_id)
    setPhase(session.phase)
    setOntologyReady(session.ontology_ready)
    setMode(session.ontology_ready ? 'qa' : 'build')
    resetPipelineState()
    setMessages([
      {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: session.ontology_ready
          ? `Session restored (${session.company || 'Unknown'}). Your ontology is ready — ask questions or explore data.`
          : `Session restored (${session.company || 'Unknown'}). Current phase: ${session.phase}.`,
        timestamp: new Date(),
      },
    ])
    setProgress(null)
  }, [])

  const handleNewSession = useCallback(() => {
    setSessionId(null)
    setMessages([])
    setPhase('intake')
    setProgress(null)
    setMode('build')
    setOntologyReady(false)
    resetPipelineState()
  }, [])

  const handleDeleteSession = useCallback(
    (id: string) => {
      deleteSession(id)
        .then(() => {
          refreshSessions()
          if (id === sessionId) handleNewSession()
        })
        .catch(() => {})
    },
    [sessionId, refreshSessions, handleNewSession]
  )

  const pushActivity = (agent: string, ph: string, status: string, detail?: string) => {
    setActivity((prev) => {
      // Update the latest entry for the same agent+phase if it's still running.
      const idx = [...prev].reverse().findIndex((e) => e.agent === agent && e.phase === ph)
      if (idx !== -1) {
        const realIdx = prev.length - 1 - idx
        const next = [...prev]
        next[realIdx] = { ...next[realIdx], status, detail: detail ?? next[realIdx].detail }
        return next
      }
      activityCounter.current += 1
      return [
        ...prev,
        { id: `act-${activityCounter.current}`, agent, phase: ph, status, detail, session_id: '' },
      ]
    })
  }

  const pipelineHandlers = useCallback(
    (): PipelineHandlers => ({
      onRunStarted: () => setLoading(true),
      onStepStarted: (step) => {
        const p = STEP_TO_PHASE[step]
        if (p) setPhase(p)
      },
      onPhaseStatus: (p) => {
        if (p.status === 'running') setPhase(p.phase)
      },
      onAgentActivity: (a) => pushActivity(a.agent, a.phase, a.status, a.detail),
      onResearchTrace: (t) => setResearchTrace(t),
      onValidationReport: () => {},
      onWorkflowOutput: (o) => {
        if (o.message) {
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: o.message!,
              timestamp: new Date(),
              phase: o.phase,
              specialistData: o.follow_up_questions
                ? { follow_up_questions: o.follow_up_questions, files: o.files }
                : undefined,
            },
          ])
        }
        if (o.ontology_ready) {
          setOntologyReady(true)
          setPhase('qa')
          if (isUpdateRun.current) {
            // Update finished — stay in the Ontology workspace, show the updated graph.
            setMode('ontology')
            setOntologyTab('graph')
          } else {
            setMode('qa')
          }
          refreshSessions()
        }
      },
      onInterrupt: (interrupts) => {
        setLoading(false)
        if (interrupts.length > 0) setPendingInterrupt(interrupts[0])
      },
      onRunFinished: () => {
        setLoading(false)
        refreshSessions()
      },
      onError: (msg) => {
        setLoading(false)
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'assistant', content: `Error: ${msg}`, timestamp: new Date() },
        ])
      },
    }),
    [refreshSessions]
  )

  // When intake completes (phase advances to 'research'), start the build pipeline once.
  useEffect(() => {
    if (sessionId && phase === 'research' && !pipelineStarted.current && !ontologyReady) {
      pipelineStarted.current = true
      isUpdateRun.current = false
      setLoading(true)
      startPipeline(sessionId, pipelineHandlers()).catch((err) => {
        setLoading(false)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `Pipeline error: ${err instanceof Error ? err.message : 'Unknown'}`,
            timestamp: new Date(),
          },
        ])
      })
    }
  }, [sessionId, phase, ontologyReady, pipelineHandlers])

  // When the user confirms an update (phase → 'update_research'), start the update pipeline once.
  useEffect(() => {
    if (sessionId && phase === 'update_research' && !updatePipelineStarted.current) {
      updatePipelineStarted.current = true
      isUpdateRun.current = true
      setActivity([])
      setResearchTrace(null)
      setLoading(true)
      startUpdatePipeline(sessionId, pipelineHandlers()).catch((err) => {
        setLoading(false)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `Update error: ${err instanceof Error ? err.message : 'Unknown'}`,
            timestamp: new Date(),
          },
        ])
      })
    }
  }, [sessionId, phase, pipelineHandlers])

  const handleApproval = useCallback(
    (approved: boolean) => {
      if (!pendingInterrupt || !sessionId) return
      setApprovalBusy(true)
      setLoading(true)
      const interruptId = pendingInterrupt.id
      setPendingInterrupt(null)
      resumeInterrupt(sessionId, interruptId, approved, pipelineHandlers(), isUpdateRun.current)
        .catch((err) => {
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: `Error: ${err instanceof Error ? err.message : 'Unknown'}`,
              timestamp: new Date(),
            },
          ])
        })
        .finally(() => {
          setApprovalBusy(false)
        })
    },
    [pendingInterrupt, sessionId, pipelineHandlers]
  )

  const handleSend = useCallback(
    async (text: string) => {
      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: text,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, userMsg])
      setLoading(true)

      try {
        if (mode === 'qa' && sessionId) {
          const res = await askOntology(sessionId, text)
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: res.answer,
              timestamp: new Date(),
              specialistData: {
                sql: res.sql,
                explanation: res.explanation,
                summary_table: res.summary_table,
                insights: res.insights,
                follow_up_questions: res.follow_up_questions,
                object_types_used: res.object_types_used,
                row_count: res.row_count,
              },
            },
          ])
          setLoading(false)
        } else {
          // Intake / update-intake — conversational REST. A pipeline effect takes over
          // once the phase advances to 'research' (build) or 'update_research' (update).
          const res = await sendMessage(text, sessionId || undefined, mode)
          setSessionId(res.session_id)
          setPhase(res.phase)
          if (res.progress) setProgress(res.progress)

          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: res.response,
              timestamp: new Date(),
              phase: res.phase,
              progress: res.progress || undefined,
              specialistData: res.specialist_data || undefined,
            },
          ])

          // Keep the loader spinning only while a pipeline is about to take over.
          if (res.phase !== 'research' && res.phase !== 'update_research') setLoading(false)
        }
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
            timestamp: new Date(),
          },
        ])
        setLoading(false)
      }
    },
    [sessionId, mode]
  )

  // Entering "Update Ontology" mode: reset the update run + change-request chat.
  const handleModeChange = useCallback((next: AppMode) => {
    // Entering the Ontology workspace defaults to the YAML tab.
    if (next === 'ontology') setOntologyTab('yaml')
    setMode(next)
  }, [])

  // Start the update flow from a batch of changes collected in the "Request changes" modal.
  const startUpdateFromBatch = useCallback(
    async (changes: string[]) => {
      if (!sessionId || changes.length === 0) return
      // Reset update run state and open the Update tab inside the Ontology workspace.
      updatePipelineStarted.current = false
      isUpdateRun.current = false
      setActivity([])
      setResearchTrace(null)
      setMode('ontology')
      setShowUpdateTab(true)
      setOntologyTab('update')
      setPhase('update_intake')

      const listMd = changes.map((c) => `- ${c}`).join('\n')
      setMessages([
        {
          id: crypto.randomUUID(),
          role: 'user',
          content: `Requested changes:\n${listMd}`,
          timestamp: new Date(),
        },
      ])
      setLoading(true)

      // The backend splits the "[BATCH]" message into individual change requests.
      const batchMessage = `[BATCH]\n${changes.join('\n')}`
      try {
        const res = await sendMessage(batchMessage, sessionId, 'update')
        setPhase(res.phase)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: res.response,
            timestamp: new Date(),
            phase: res.phase,
            specialistData: res.specialist_data || undefined,
          },
        ])
        if (res.phase !== 'update_research') setLoading(false)
      } catch (err) {
        setLoading(false)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
            timestamp: new Date(),
          },
        ])
      }
    },
    [sessionId]
  )

  // Chat send inside the Update tab (follow-up answers, "done", "confirm").
  const handleUpdateSend = useCallback(
    async (text: string) => {
      if (!sessionId) return
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', content: text, timestamp: new Date() },
      ])
      setLoading(true)
      try {
        const res = await sendMessage(text, sessionId, 'update')
        setPhase(res.phase)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: res.response,
            timestamp: new Date(),
            phase: res.phase,
            specialistData: res.specialist_data || undefined,
          },
        ])
        if (res.phase !== 'update_research') setLoading(false)
      } catch (err) {
        setLoading(false)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
            timestamp: new Date(),
          },
        ])
      }
    },
    [sessionId]
  )

  const currentCompany = sessions.find((s) => s.session_id === sessionId)?.company || null
  const showPipelinePanels = activity.length > 0 || researchTrace

  return (
    <div className="flex h-screen bg-background text-foreground">
      <Sidebar
        mode={mode}
        onModeChange={handleModeChange}
        ontologyReady={ontologyReady}
        sessions={sessions}
        currentSessionId={sessionId}
        currentCompany={currentCompany}
        onSelectSession={selectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onRefreshSessions={refreshSessions}
        skillsSlot={<SkillsPanel activePhase={phase} />}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border px-6 py-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold">{MODE_TITLES[mode]}</h1>
            <Badge variant={ontologyReady ? 'success' : 'info'} className="gap-1">
              {ontologyReady ? <Sparkles className="size-3" /> : null}
              {PHASE_LABELS[phase] || phase}
            </Badge>
          </div>
          <button
            onClick={toggleTheme}
            className="flex size-9 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
        </header>

        {mode === 'build' && (
          <div className="border-b border-border bg-card/40">
            <PhaseTimeline
              phase={phase}
              loading={loading}
              block={progress?.block}
              totalBlocks={progress?.total_blocks ?? 7}
              variant="build"
            />
          </div>
        )}

        <main className="min-h-0 flex-1 overflow-hidden">
          {mode === 'ontology' && sessionId ? (
            <OntologyViewer
              sessionId={sessionId}
              onRequestChanges={startUpdateFromBatch}
              tab={ontologyTab}
              onTabChange={setOntologyTab}
              showUpdateTab={showUpdateTab}
              updateSlot={
                <div className="flex h-full flex-col">
                  <div className="border-b border-border bg-card/40">
                    <PhaseTimeline phase={phase} loading={loading} variant="update" />
                  </div>
                  <div className="flex min-h-0 flex-1">
                    <div className="min-w-0 flex-1">
                      <ChatPanel
                        messages={messages}
                        onSend={handleUpdateSend}
                        loading={loading}
                        mode="update"
                      />
                    </div>
                    {showPipelinePanels && (
                      <div className="w-80 shrink-0 space-y-3 overflow-y-auto border-l border-border bg-card/30 p-4">
                        <AgentActivity entries={activity} />
                        {researchTrace && <ResearchTrace trace={researchTrace} />}
                      </div>
                    )}
                  </div>
                </div>
              }
            />
          ) : mode === 'data' && sessionId ? (
            <DataExplorer sessionId={sessionId} />
          ) : (
            <div className="flex h-full">
              <div className="min-w-0 flex-1">
                <ChatPanel messages={messages} onSend={handleSend} loading={loading} mode={mode} />
              </div>
              {mode === 'build' && showPipelinePanels && (
                <div className="w-80 shrink-0 space-y-3 overflow-y-auto border-l border-border bg-card/30 p-4">
                  <AgentActivity entries={activity} />
                  {researchTrace && <ResearchTrace trace={researchTrace} />}
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      {pendingInterrupt && (
        <ApprovalDialog
          interrupt={pendingInterrupt}
          busy={approvalBusy}
          onApprove={() => handleApproval(true)}
          onDeny={() => handleApproval(false)}
        />
      )}
    </div>
  )
}

export default App
