export type NodeType = string

export type ExecutionStatus = 'created' | 'running' | 'success' | 'failed'

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
}

export interface EdgeCreatePayload {
  workflow_id: number
  source_node_id: number
  target_node_id: number
}

export interface EdgeResponse {
  id: number
  workflow_id: number
  source_node_id: number
  target_node_id: number
}

export interface Execution {
  id: number
  workflow_id: number
  status: ExecutionStatus
  input_data: RunInputPayload | null
  output_data: Record<string, unknown> | null
  error: string | null
  prefect_flow_run_id: string | null
  started_at: string
  finished_at: string | null
}

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
  | 'select'
  | 'provider'
  | 'model'

export type NodeFieldDataSourceKind = 'llm_provider' | 'llm_model'

export interface NodeCatalogGraph {
  has_input: boolean
  has_output: boolean
}

export interface NodeCatalogFieldUI {
  widget: NodeFieldWidget
  label: string
  placeholder: string | null
  help: string | null
}

export interface NodeCatalogFieldDataSource {
  kind: NodeFieldDataSourceKind
  depends_on: string | null
}

export interface NodeCatalogField {
  name: string
  required: boolean
  validators: NodeFieldValidator
  ui: NodeCatalogFieldUI
  default: unknown
  datasource: NodeCatalogFieldDataSource | null
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
}

export interface LlmModel {
  name: string
}

export interface ApiError {
  message: string
  status: number
}
