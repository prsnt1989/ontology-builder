const API_BASE = '/api'

export interface ChatResponse {
  session_id: string
  response: string
  phase: string
  progress?: {
    block: number
    total_blocks: number
    phase: string
  }
  specialist_data?: Record<string, unknown>
  ontology_ready: boolean
}

export interface AskResponse {
  answer: string
  sql: string
  explanation: string
  object_types_used: string[]
  summary_table?: {
    headers: string[]
    rows: string[][]
  }
  insights: string[]
  follow_up_questions: string[]
  row_count: number
}

export interface TableInfo {
  table_name: string
  column_count: number
  row_count: number
}

export async function sendMessage(
  message: string,
  sessionId?: string,
  mode: string = 'build'
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, mode }),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function askOntology(
  sessionId: string,
  question: string
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ontology/${sessionId}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getTables(sessionId: string): Promise<{ tables: TableInfo[] }> {
  const res = await fetch(`${API_BASE}/data/${sessionId}/tables`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getTableData(
  sessionId: string,
  tableName: string,
  limit = 50,
  offset = 0
): Promise<{ table_name: string; columns: string[]; rows: Record<string, unknown>[]; total_rows: number }> {
  const res = await fetch(`${API_BASE}/data/${sessionId}/tables/${tableName}?limit=${limit}&offset=${offset}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export interface OntologyFileInfo {
  name: string
  size: number
}

export async function getOntologyFiles(sessionId: string): Promise<{ files: OntologyFileInfo[]; session_id: string }> {
  const res = await fetch(`${API_BASE}/ontology/${sessionId}/files`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getOntologyFileContent(sessionId: string, filename: string): Promise<string> {
  const res = await fetch(`${API_BASE}/ontology/${sessionId}/files/${filename}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.text()
}

export interface SessionInfo {
  session_id: string
  phase: string
  created_at: string | null
  company: string | null
  ontology_ready: boolean
}

export async function listSessions(): Promise<{ sessions: SessionInfo[] }> {
  const res = await fetch(`${API_BASE}/sessions`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
}

export interface GraphProperty {
  name: string
  display_name?: string
  description?: string
  type?: string
  required?: boolean
  unique?: boolean
  indexed?: boolean
  enum_values?: string[]
}

export interface GraphObjectType {
  api_name: string
  display_name: string
  plural_display_name?: string
  description?: string
  primary_key?: string
  icon?: string | null
  title_property?: string
  backing_table?: { table_name?: string } | null
  properties?: GraphProperty[]
}

export interface GraphRelationship {
  api_name: string
  display_name: string
  description?: string
  from_object_type: string
  to_object_type: string
  cardinality: 'one_to_one' | 'one_to_many' | 'many_to_one' | 'many_to_many' | string
  inverse_name?: string | null
  is_required?: boolean
}

export interface OntologyGraphData {
  object_types: GraphObjectType[]
  relationships: GraphRelationship[]
}

export async function getOntologyGraph(sessionId: string): Promise<OntologyGraphData> {
  const res = await fetch(`${API_BASE}/ontology/${sessionId}/graph`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export interface SkillInfo {
  name: string
  description: string
  phase: string | null
}

export async function listSkills(): Promise<{ skills: SkillInfo[] }> {
  const res = await fetch(`${API_BASE}/skills`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}
