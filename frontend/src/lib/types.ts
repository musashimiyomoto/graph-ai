export type NodeType = 'input' | 'llm' | 'output'

export type ExecutionStatus = 'created' | 'running' | 'success' | 'failed'

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
  input_data: object | null
  output_data: object | null
  error: string | null
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

export interface NodeField {
  name: string
  validators: NodeFieldValidator
}

export interface LlmProvider {
  id: number
  user_id: number
  name: string
  type: string
  base_url: string | null
}

export interface LlmProviderCreatePayload {
  name: string
  type: string
  base_url: string
}

export interface LlmModel {
  name: string
}

export interface ApiError {
  message: string
  status: number
}
