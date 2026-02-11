import type {
  EdgeCreatePayload,
  EdgeResponse,
  Execution,
  LlmModel,
  LlmProvider,
  LlmProviderCreatePayload,
  NodeCatalogItem,
  NodeCreatePayload,
  NodeResponse,
  NodeUpdatePayload,
  RunInputPayload,
  TokenResponse,
  UserProfile,
  Workflow,
} from './types'

const BASE = '/api'

let currentToken: string | null = null

export function setToken(token: string | null): void {
  currentToken = token
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) ?? {}),
  }

  if (currentToken) {
    headers['Authorization'] = `Bearer ${currentToken}`
  }

  const response = await fetch(`${BASE}${path}`, { ...options, headers })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const message =
      (body as { detail?: string }).detail ?? response.statusText
    throw { message, status: response.status }
  }

  return (await response.json()) as T
}

export async function login(
  email: string,
  password: string,
): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function register(
  email: string,
  password: string,
): Promise<UserProfile> {
  return request<UserProfile>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function getMe(): Promise<UserProfile> {
  return request<UserProfile>('/users/me')
}

export async function deleteMe(): Promise<void> {
  await request('/users/me', { method: 'DELETE' })
}

export async function getWorkflows(): Promise<Workflow[]> {
  return request<Workflow[]>('/workflows')
}

export async function createWorkflow(name: string): Promise<Workflow> {
  return request<Workflow>('/workflows', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export async function updateWorkflow(
  workflowId: number,
  name: string,
): Promise<Workflow> {
  return request<Workflow>(`/workflows/${workflowId}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export async function deleteWorkflow(workflowId: number): Promise<void> {
  await request(`/workflows/${workflowId}`, { method: 'DELETE' })
}

export async function getNodes(
  workflowId: number,
): Promise<NodeResponse[]> {
  return request<NodeResponse[]>(`/nodes?workflow_id=${workflowId}`)
}

export async function createNode(
  payload: NodeCreatePayload,
): Promise<NodeResponse> {
  return request<NodeResponse>('/nodes', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateNode(
  nodeId: number,
  payload: NodeUpdatePayload,
): Promise<NodeResponse> {
  return request<NodeResponse>(`/nodes/${nodeId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteNode(nodeId: number): Promise<void> {
  await request(`/nodes/${nodeId}`, { method: 'DELETE' })
}

export async function getNodeCatalog(): Promise<NodeCatalogItem[]> {
  return request<NodeCatalogItem[]>('/nodes/catalog')
}

export async function getEdges(
  workflowId: number,
): Promise<EdgeResponse[]> {
  return request<EdgeResponse[]>(`/edges?workflow_id=${workflowId}`)
}

export async function createEdge(
  payload: EdgeCreatePayload,
): Promise<EdgeResponse> {
  return request<EdgeResponse>('/edges', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteEdge(edgeId: number): Promise<void> {
  await request(`/edges/${edgeId}`, { method: 'DELETE' })
}

export async function getExecutions(
  workflowId: number,
): Promise<Execution[]> {
  return request<Execution[]>(`/executions?workflow_id=${workflowId}`)
}

export async function createExecution(
  workflowId: number,
  inputData: RunInputPayload,
): Promise<Execution> {
  return request<Execution>('/executions', {
    method: 'POST',
    body: JSON.stringify({ workflow_id: workflowId, input_data: inputData }),
  })
}

export async function getLlmProviders(): Promise<LlmProvider[]> {
  return request<LlmProvider[]>('/llm-providers')
}

export async function createLlmProvider(
  payload: LlmProviderCreatePayload,
): Promise<LlmProvider> {
  return request<LlmProvider>('/llm-providers', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteLlmProvider(providerId: number): Promise<void> {
  await request(`/llm-providers/${providerId}`, { method: 'DELETE' })
}

export async function getLlmProviderModels(
  providerId: number,
): Promise<LlmModel[]> {
  return request<LlmModel[]>(`/llm-providers/${providerId}/models`)
}
