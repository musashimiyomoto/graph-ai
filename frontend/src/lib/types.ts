export type NodeType = string

export type ExecutionStatus =
  | 'created'
  | 'running'
  | 'waiting_approval'
  | 'waiting_delay'
  | 'success'
  | 'failed'
  | 'cancelled'
  | 'rejected'

export const ACTIVE_STATUSES: ExecutionStatus[] = [
  'created',
  'running',
  'waiting_approval',
  'waiting_delay',
]

// What triggered an execution: the owner testing the flow, or real inbound
// traffic (channel messages or a cron schedule firing). Lets the UI split
// "Test Runs" (a sandbox for trying the flow before it's relied on) from
// "Activity Log" (real usage) instead of merging them into one list.
export type ExecutionSource = string

export interface RunInputPayload {
  value: string
}

export interface TriggerActor {
  id: string | null
  display_name: string | null
  address: string | null
}

export interface TriggerConversation {
  id: string
  thread_id: string | null
}

export interface TriggerEvent {
  schema_version: 1
  channel: ExecutionSource
  external_event_id: string | null
  sender: TriggerActor | null
  conversation: TriggerConversation | null
  locale: string | null
  message: NodeValueEnvelope
  attachments: NodeValueEnvelope[]
  occurred_at: string
  metadata: Record<string, unknown>
  raw_retention: 'discard'
}

export interface Workflow {
  id: number
  owner_id: number
  name: string
  webhook_path: string
  web_chat_path: string
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
  target_handle?: string | null
  coercion?: PortCoercion | null
}

export interface EdgeResponse {
  id: number
  workflow_id: number
  source_node_id: number
  target_node_id: number
  source_handle: string | null
  target_handle: string | null
  coercion: PortCoercion | null
}

export interface Execution {
  id: number
  workflow_id: number
  version_id: number | null
  status: ExecutionStatus
  source: ExecutionSource
  input_data: RunInputPayload | null
  trigger_event: TriggerEvent
  output_data: Record<string, unknown> | null
  error: string | null
  approval_node_id: number | null
  approval_prompt: string | null
  approval_input: string | null
  queue_job_id: string | null
  wait_until: string | null
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
  target_handle: string | null
  coercion?: PortCoercion | null
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
  email_verified_at: string | null
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface MessageResponse {
  detail: string
}

export interface AuthSession {
  id: number
  created_at: string
  last_used_at: string
  expires_at: string
  user_agent: string | null
  ip_address: string | null
  current: boolean
}

export interface NodeFieldValidator {
  min_length?: number
  select?: string[]
  ge?: number
  le?: number
  url?: boolean
  datetime?: boolean
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
  | 'email_account'
  | 'vector_collection'
  | 'postgres_connection'
  | 'workflow'
  | 'switch_branches'
  | 'mcp_server'
  | 'mcp_tool'

export type NodeFieldDataSourceKind =
  | 'llm_provider'
  | 'llm_model'
  | 'telegram_bot'
  | 'email_account'
  | 'vector_collection'
  | 'postgres_connection'
  | 'workflow'
  | 'mcp_server'
  | 'mcp_tool'

export type PortType = 'text' | 'json' | 'file' | 'list' | 'image' | 'audio' | 'video'

export type PortCoercion =
  | 'text_to_json'
  | 'json_to_text'
  | 'text_to_list'
  | 'list_to_text'
  | 'json_to_list'
  | 'list_to_json'
  | 'image_to_file'
  | 'audio_to_file'
  | 'video_to_file'

export interface NodePortSpec {
  name: string
  label: string
  type: PortType
  required: boolean
  type_field: string | null
  allowed_types: PortType[]
}

export interface NodeCatalogGraph {
  has_input: boolean
  has_output: boolean
  input_port: PortType | null
  output_port: PortType | null
  output_handles: string[] | null
  inputs: NodePortSpec[]
  outputs: NodePortSpec[]
}

export interface NodeCatalogFieldUI {
  widget: NodeFieldWidget
  label: string
  placeholder: string | null
  help: string | null
  step: number | null
  options: Record<string, string>
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

export interface ChannelCapabilities {
  receive: boolean
  acknowledge: boolean
  deliver: boolean
}

export interface ChannelSettings {
  key: string
  label: string
  component_key: string
}

export interface ChannelCatalogItem {
  source: ExecutionSource
  label: string
  icon_key: string
  input_format: string | null
  output_format: string | null
  activity: boolean
  capabilities: ChannelCapabilities
  poll_seconds: number[] | null
  settings: ChannelSettings | null
  input_fields: NodeCatalogField[]
  output_fields: NodeCatalogField[]
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

export interface EmailAccount {
  id: number
  user_id: number
  name: string
  email_address: string
  username: string
  imap_host: string
  imap_port: number
  imap_use_ssl: boolean
  smtp_host: string
  smtp_port: number
  smtp_use_tls: boolean
  smtp_use_ssl: boolean
  enabled: boolean
}

export interface EmailAccountCreatePayload {
  name: string
  email_address: string
  username: string
  password: string
  imap_host: string
  imap_port: number
  imap_use_ssl: boolean
  smtp_host: string
  smtp_port: number
  smtp_use_tls: boolean
  smtp_use_ssl: boolean
}

export interface PostgresConnection {
  id: number
  user_id: number
  name: string
}

export interface PostgresConnectionCreatePayload {
  name: string
  dsn: string
}

export interface MCPServer {
  id: number
  user_id: number
  name: string
  url: string
  has_headers: boolean
}

export interface MCPServerCreatePayload {
  name: string
  url: string
  headers: Record<string, string>
}

export interface MCPTool {
  name: string
  description: string | null
  input_schema: Record<string, unknown>
}

export interface MCPRegistryInput {
  key: string
  description: string | null
  placeholder: string | null
  default: string | null
  required: boolean
  secret: boolean
}

export interface MCPRegistryServer {
  registry_name: string
  name: string
  description: string | null
  version: string
  url_template: string
  header_templates: Record<string, string>
  inputs: MCPRegistryInput[]
  repository_url: string | null
}

export interface NodeExecutionResult {
  id: number
  execution_id: number
  node_id: number
  node_type: NodeType | null
  node_label: string | null
  status: ExecutionStatus
  output: string | null
  output_value: NodeValueEnvelope | null
  output_values: Record<string, NodeValueEnvelope> | null
  error: string | null
  started_at: string
  finished_at: string | null
  wait_until: string | null
  iteration: number | null
}

export interface ArtifactReference {
  artifact_id: number
  mime_type: string
  size: number
  checksum: string
  filename: string | null
}

export interface NodeValueEnvelope {
  kind: PortType
  value: unknown
  artifact: ArtifactReference | null
  metadata: Record<string, unknown>
}

export interface ArtifactDownload {
  url: string
  expires_at: string
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
