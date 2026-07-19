export interface ValidationIssue {
  severity: 'critical' | 'warning' | 'suggestion'
  category: string
  component: string
  message: string
  suggestion?: string
}

export interface SpecialistData {
  // Update-flow marker (e.g. 'gathering' | 'captured' | 'summary'); used to
  // suppress the QA-only follow-up chip renderer during update follow-ups.
  kind?: string
  sql?: string
  explanation?: string
  summary_table?: { headers: string[]; rows: string[][] }
  insights?: string[]
  follow_up_questions?: string[]
  object_types_used?: string[]
  row_count?: number
  // Validation phase
  issues?: ValidationIssue[]
  overall_score?: number
  passed?: boolean
  strengths?: string[]
  summary?: string
  // Generation phase
  files?: string[]
  tables_created?: string[]
  seed_counts?: Record<string, number>
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  phase?: string
  progress?: {
    block: number
    total_blocks: number
    phase: string
  }
  specialistData?: SpecialistData
}

export type AppMode = 'build' | 'qa' | 'ontology' | 'data'

export interface SessionState {
  sessionId: string | null
  phase: string
  mode: AppMode
  ontologyReady: boolean
  messages: Message[]
}
