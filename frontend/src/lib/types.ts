export type NodeType = string

export type ExecutionStatus = 'created' | 'running' | 'success' | 'failed'

export const ACTIVE_STATUSES: ExecutionStatus[] = ['created', 'running']

// What triggered an execution: the owner testing the flow, or real inbound
// traffic (Telegram messages or a cron schedule firing). Lets the UI split
// "Test Runs" (a sandbox for trying the flow before it's relied on) from
// "Activity Log" (real usage) instead of merging them into one list.
export type ExecutionSource = 'manual' | 'telegram' | 'schedule'

export interface RunInputPayload {
  value: string
}

export interface Workflow {
  id: number
  owner_id: number
  name: string
  created_at: string
  updated_at: string
}

export interface NodeCreatePayload {
  workflow_id: number
  type: NodeType
  data: Record<string, unknown>
  position_x: number
  position_y: number
  parent_node_id?: number | null
}

export interface NodeUpdatePayload {
  data?: Record<string, unknown>
  position_x?: number
  position_y?: number
}

export interface NodeResponse {
  id: number
  workflow_id: number
  type: NodeType
  data: Record<string, unknown>
  position_x: number
  position_y: number
  parent_node_id: number | null
}

export interface EdgeCreatePayload {
  workflow_id: number
  source_node_id: number
  target_node_id: number
  source_handle?: string | null
}

export interface EdgeResponse {
  id: number
  workflow_id: number
  source_node_id: number
  target_node_id: number
  source_handle: string | null
}

export interface Execution {
  id: number
  workflow_id: number
  version_id: number | null
  status: ExecutionStatus
  source: ExecutionSource
  input_data: RunInputPayload | null
  output_data: Record<string, unknown> | null
  error: string | null
  prefect_flow_run_id: string | null
  started_at: string
  finished_at: string | null
}

export interface NodeMeta {
  type: string
  label: string
  portType: PortType | null
  parentNodeId: number | null
}

export interface WorkflowVersion {
  id: number
  workflow_id: number
  version: number
  created_at: string
}

// Portable graph shape shared by export/import/duplicate/templates. Nodes
// carry no ID — a transfer always creates fresh nodes; edges reference nodes
// by their (0-based) position in `nodes` since node IDs don't exist yet at
// import time and an export's IDs are meaningless to a different workflow.
export interface WorkflowGraphNode {
  type: NodeType
  data: Record<string, unknown>
  position_x: number
  position_y: number
  parent_index: number | null
}

export interface WorkflowGraphEdge {
  source_index: number
  target_index: number
  source_handle: string | null
}

export interface WorkflowGraphTransfer {
  nodes: WorkflowGraphNode[]
  edges: WorkflowGraphEdge[]
}

export interface WorkflowExport {
  name: string
  graph: WorkflowGraphTransfer
}

export interface WorkflowTemplate {
  key: string
  name: string
  description: string
}

export interface TokenStreamEvent {
  type: 'token'
  node_id: number
  delta: string
}

// A node is retrying: its already-streamed text should be discarded before
// the retry's fresh deltas start arriving, so the live view doesn't show the
// failed attempt's partial text followed by the full retried response.
export interface TokenResetStreamEvent {
  type: 'token_reset'
  node_id: number
}

export interface StatusStreamEvent {
  type: 'status'
  execution: Execution
}

export interface ExpiredStreamEvent {
  type: 'expired'
}

export type ExecutionStreamEvent =
  | TokenStreamEvent
  | TokenResetStreamEvent
  | StatusStreamEvent
  | ExpiredStreamEvent

export interface UserProfile {
  id: number
  email: string
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface NodeFieldValidator {
  min_length?: number
  select?: string[]
  ge?: number
  le?: number
}

export type NodeFieldWidget =
  | 'text'
  | 'textarea'
  | 'number'
  | 'optional_number'
  | 'select'
  | 'provider'
  | 'model'
  | 'telegram_bot'
  | 'vector_collection'

export type NodeFieldDataSourceKind =
  | 'llm_provider'
  | 'llm_model'
  | 'telegram_bot'
  | 'vector_collection'

export type PortType = 'text' | 'json' | 'file' | 'list'

export interface NodeCatalogGraph {
  has_input: boolean
  has_output: boolean
  input_port: PortType | null
  output_port: PortType | null
  output_handles: string[] | null
}

export interface NodeCatalogFieldUI {
  widget: NodeFieldWidget
  label: string
  placeholder: string | null
  help: string | null
  step: number | null
}

export interface NodeCatalogFieldDataSource {
  kind: NodeFieldDataSourceKind
  depends_on: string | null
}

export interface NodeCatalogFieldVisibility {
  field: string
  equals: unknown
  not_equals: unknown
}

export interface NodeCatalogField {
  name: string
  required: boolean
  validators: NodeFieldValidator
  ui: NodeCatalogFieldUI
  default: unknown
  datasource: NodeCatalogFieldDataSource | null
  visible_when: NodeCatalogFieldVisibility | null
}

export interface NodeCatalogItem {
  type: NodeType
  label: string
  icon_key: string
  graph: NodeCatalogGraph
  fields: NodeCatalogField[]
}

export interface LlmProvider {
  id: number
  user_id: number
  name: string
  type: string
  base_url: string
  config: Record<string, unknown>
}

export interface LlmProviderCreatePayload {
  name: string
  type: string
  base_url: string
  config?: Record<string, unknown>
  api_key?: string | null
}

export interface LlmModel {
  name: string
}

export interface OllamaCatalogTag {
  tag: string
  size_gb: number
  params: string
}

export interface OllamaCatalogEntry {
  name: string
  description: string
  tags: OllamaCatalogTag[]
}

export interface OllamaPullJob {
  job_id: string
  model: string
}

export interface OllamaPullEvent {
  status: string
  percent?: number
  done?: boolean
  error?: string
}

export interface TelegramBot {
  id: number
  user_id: number
  name: string
  enabled: boolean
}

export interface TelegramBotCreatePayload {
  name: string
  bot_token: string
}

export interface NodeExecutionResult {
  id: number
  execution_id: number
  node_id: number
  node_type: NodeType | null
  node_label: string | null
  status: ExecutionStatus
  output: string | null
  error: string | null
  started_at: string
  finished_at: string | null
  iteration: number | null
}

export interface VectorCollection {
  name: string
  point_count: number
}

export interface VectorDocument {
  source: string
  chunk_count: number
}

export interface VectorUploadJob {
  job_id: string
  source: string
}

export interface VectorJobStatus {
  status: 'processing' | 'ready' | 'failed'
  chunks_ingested: number | null
  detail: string | null
}

export interface ApiError {
  message: string
  status: number
}
