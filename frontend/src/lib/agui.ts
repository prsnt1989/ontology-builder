// AG-UI SSE client for the ontology build pipeline (POST /api/pipeline).
//
// Parses the Server-Sent Events stream emitted by the MAF workflow and dispatches
// typed callbacks. Event shapes are verified against the backend:
//   RUN_STARTED, STEP_STARTED/STEP_FINISHED (phase timeline),
//   CUSTOM {name: phase_status | agent_activity | research_trace | validation_report
//           | workflow_output | status}, RUN_FINISHED {outcome:{type:'interrupt', interrupts:[...]}}

const PIPELINE_URL = '/api/pipeline'
const UPDATE_PIPELINE_URL = '/api/pipeline/update'

export interface PhaseStatus {
  session_id: string
  phase: string
  status: 'running' | 'done' | 'failed' | 'skipped'
  summary?: string
}

export interface AgentActivity {
  session_id: string
  phase: string
  agent: string
  status: string
  detail?: string
}

export interface ResearchTrace {
  session_id: string
  industry?: string
  domain?: string
  recommended_object_types?: unknown[]
  industry_patterns?: unknown[]
  best_practices?: string[]
  sources?: unknown[]
}

export interface ValidationReport {
  session_id: string
  overall_score?: number
  passed?: boolean
  issues?: { severity: string; message: string; suggestion?: string; category?: string }[]
  strengths?: string[]
}

export interface WorkflowOutput {
  phase: string
  status: string
  message?: string
  ontology_ready?: boolean
  files?: string[]
  tables_created?: string[]
  seed_counts?: Record<string, number>
  follow_up_questions?: string[]
}

export interface PendingInterrupt {
  id: string
  reason?: string
  responseSchema?: unknown
  data: {
    session_id: string
    kind: string
    title: string
    detail: string
    tables?: string[]
  }
}

export interface PipelineHandlers {
  onRunStarted?: () => void
  onStepStarted?: (step: string) => void
  onStepFinished?: (step: string) => void
  onPhaseStatus?: (p: PhaseStatus) => void
  onAgentActivity?: (a: AgentActivity) => void
  onResearchTrace?: (t: ResearchTrace) => void
  onValidationReport?: (r: ValidationReport) => void
  onWorkflowOutput?: (o: WorkflowOutput) => void
  onInterrupt?: (interrupts: PendingInterrupt[]) => void
  onRunFinished?: () => void
  onError?: (message: string) => void
}

function extractInterrupts(outcome: unknown): PendingInterrupt[] {
  if (!outcome || typeof outcome !== 'object') return []
  const o = outcome as { type?: string; interrupts?: unknown[] }
  if (o.type !== 'interrupt' || !Array.isArray(o.interrupts)) return []
  return o.interrupts
    .map((it) => {
      const rec = it as Record<string, unknown>
      const meta = (rec.metadata as Record<string, unknown> | undefined)?.agent_framework as
        | Record<string, unknown>
        | undefined
      const data = (meta?.data ?? rec.data) as PendingInterrupt['data']
      return {
        id: String(rec.id ?? meta?.request_id ?? ''),
        reason: rec.reason as string | undefined,
        responseSchema: rec.responseSchema,
        data,
      }
    })
    .filter((i) => i.id && i.data)
}

async function consumeStream(body: string, handlers: PipelineHandlers, url: string = PIPELINE_URL): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body,
  })
  if (!res.ok || !res.body) {
    handlers.onError?.(`Pipeline error: ${res.status}`)
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (raw: string) => {
    const dataLines = raw
      .split('\n')
      .filter((l) => l.startsWith('data:'))
      .map((l) => l.slice(5).trim())
    if (dataLines.length === 0) return
    const payload = dataLines.join('\n')
    let e: Record<string, unknown>
    try {
      e = JSON.parse(payload)
    } catch {
      return
    }
    handleEvent(e, handlers)
  }

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const chunk = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      dispatch(chunk)
    }
  }
  if (buffer.trim()) dispatch(buffer)
}

function handleEvent(e: Record<string, unknown>, h: PipelineHandlers): void {
  const type = e.type as string
  switch (type) {
    case 'RUN_STARTED':
      h.onRunStarted?.()
      break
    case 'STEP_STARTED':
      h.onStepStarted?.(String(e.stepName ?? e.step_name ?? ''))
      break
    case 'STEP_FINISHED':
      h.onStepFinished?.(String(e.stepName ?? e.step_name ?? ''))
      break
    case 'CUSTOM': {
      const name = e.name as string
      const value = e.value as Record<string, unknown>
      if (name === 'phase_status') h.onPhaseStatus?.(value as unknown as PhaseStatus)
      else if (name === 'agent_activity') h.onAgentActivity?.(value as unknown as AgentActivity)
      else if (name === 'research_trace') h.onResearchTrace?.(value as unknown as ResearchTrace)
      else if (name === 'validation_report')
        h.onValidationReport?.(value as unknown as ValidationReport)
      else if (name === 'workflow_output') h.onWorkflowOutput?.(value as unknown as WorkflowOutput)
      break
    }
    case 'RUN_ERROR':
      h.onError?.(String(e.message ?? 'Pipeline run error'))
      break
    case 'RUN_FINISHED': {
      const interrupts = extractInterrupts(e.outcome)
      if (interrupts.length > 0) h.onInterrupt?.(interrupts)
      else h.onRunFinished?.()
      break
    }
    default:
      break
  }
}

/** Start the build pipeline for a session. thread_id == session_id. */
export function startPipeline(sessionId: string, handlers: PipelineHandlers): Promise<void> {
  return consumeStream(
    JSON.stringify({
      thread_id: sessionId,
      run_id: `run-${Date.now()}`,
      messages: [{ role: 'user', content: 'start pipeline' }],
    }),
    handlers
  )
}

/** Start the update pipeline (applies confirmed ontology changes). */
export function startUpdatePipeline(sessionId: string, handlers: PipelineHandlers): Promise<void> {
  return consumeStream(
    JSON.stringify({
      thread_id: sessionId,
      run_id: `upd-${Date.now()}`,
      messages: [{ role: 'user', content: 'apply updates' }],
    }),
    handlers,
    UPDATE_PIPELINE_URL
  )
}

/** Resume a paused pipeline by resolving an interrupt (e.g. approval). */
export function resumeInterrupt(
  sessionId: string,
  interruptId: string,
  payload: unknown,
  handlers: PipelineHandlers,
  isUpdate = false
): Promise<void> {
  return consumeStream(
    JSON.stringify({
      thread_id: sessionId,
      run_id: `run-${Date.now()}`,
      messages: [],
      resume: [{ interruptId, status: 'resolved', payload }],
    }),
    handlers,
    isUpdate ? UPDATE_PIPELINE_URL : PIPELINE_URL
  )
}
