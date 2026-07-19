import type {
  ApiError,
  EdgeCreatePayload,
  EdgeResponse,
  EmailAccount,
  EmailAccountCreatePayload,
  Execution,
  ExecutionSource,
  ExecutionStreamEvent,
  LlmModel,
  LlmProvider,
  LlmProviderCreatePayload,
  NodeCatalogItem,
  NodeCreatePayload,
  NodeExecutionResult,
  NodeResponse,
  NodeUpdatePayload,
  OllamaCatalogEntry,
  OllamaPullEvent,
  OllamaPullJob,
  PostgresConnection,
  PostgresConnectionCreatePayload,
  RunInputPayload,
  TelegramBot,
  TelegramBotCreatePayload,
  TokenResponse,
  UserProfile,
  VectorCollection,
  VectorDocument,
  VectorJobStatus,
  VectorUploadJob,
  Workflow,
  WorkflowExport,
  WorkflowGraphTransfer,
  WorkflowTemplate,
  WorkflowVersion,
} from './types'

const BASE = '/api'

let currentToken: string | null = null

export function setToken(token: string | null): void {
  currentToken = token
}

export function publicWebhookUrl(webhookPath: string): string {
  return new URL(`${BASE}${webhookPath}`, window.location.origin).toString()
}

export function webChatEmbedSnippet(webChatPath: string): string {
  const loaderUrl = new URL('/graph-ai-chat.js', window.location.origin).toString()
  const endpoint = new URL(`${BASE}${webChatPath}`, window.location.origin).toString()
  return `<script src="${loaderUrl}" data-endpoint="${endpoint}" async></script>`
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  // A FormData body (file upload) must not get a forced JSON content type —
  // the browser sets its own multipart boundary.
  const isFormData = options.body instanceof FormData
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...((options.headers as Record<string, string>) ?? {}),
  }

  if (currentToken) {
    headers['Authorization'] = `Bearer ${currentToken}`
  }

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { ...options, headers })
  } catch {
    // fetch() throws a raw TypeError for network-level failures (dropped
    // connection, DNS, CORS, offline, ...) rather than an ApiError; normalize
    // it here so callers only ever have to handle one error shape.
    const networkError: ApiError = {
      message: 'Network error — check your connection.',
      status: 0,
    }
    throw networkError
  }

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

export async function getWorkflowVersions(
  workflowId: number,
): Promise<WorkflowVersion[]> {
  return request<WorkflowVersion[]>(`/workflows/${workflowId}/versions`)
}

export async function exportWorkflow(workflowId: number): Promise<WorkflowExport> {
  return request<WorkflowExport>(`/workflows/${workflowId}/export`)
}

export async function importWorkflow(
  name: string,
  graph: WorkflowGraphTransfer,
): Promise<Workflow> {
  return request<Workflow>('/workflows/import', {
    method: 'POST',
    body: JSON.stringify({ name, graph }),
  })
}

export async function duplicateWorkflow(workflowId: number): Promise<Workflow> {
  return request<Workflow>(`/workflows/${workflowId}/duplicate`, {
    method: 'POST',
  })
}

export async function getWorkflowTemplates(): Promise<WorkflowTemplate[]> {
  return request<WorkflowTemplate[]>('/workflow-templates')
}

export async function instantiateWorkflowTemplate(
  templateKey: string,
  name?: string,
): Promise<Workflow> {
  return request<Workflow>(`/workflow-templates/${templateKey}/instantiate`, {
    method: 'POST',
    body: JSON.stringify(name ? { name } : {}),
  })
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
  source?: ExecutionSource[],
): Promise<Execution[]> {
  const params = new URLSearchParams({ workflow_id: String(workflowId) })
  for (const value of source ?? []) {
    params.append('source', value)
  }
  return request<Execution[]>(`/executions?${params.toString()}`)
}

export async function getExecutionNodeResults(
  executionId: number,
): Promise<NodeExecutionResult[]> {
  return request<NodeExecutionResult[]>(`/executions/${executionId}/nodes`)
}

export async function cancelExecution(executionId: number): Promise<Execution> {
  return request<Execution>(`/executions/${executionId}/cancel`, {
    method: 'POST',
  })
}

export async function streamExecution(
  executionId: number,
  onEvent: (event: ExecutionStreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {}
  if (currentToken) {
    headers['Authorization'] = `Bearer ${currentToken}`
  }

  const response = await fetch(`${BASE}/executions/${executionId}/stream`, {
    headers,
    signal,
  })

  if (!response.ok || !response.body) {
    throw { message: 'Stream failed', status: response.status } as ApiError
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      const dataLine = frame
        .split('\n')
        .find((line) => line.startsWith('data:'))
      if (!dataLine) {
        continue
      }

      const payload = dataLine.slice('data:'.length).trim()
      if (!payload) {
        continue
      }
      try {
        onEvent(JSON.parse(payload) as ExecutionStreamEvent)
      } catch {
        // Skip a malformed frame rather than killing the whole stream.
      }
    }
  }
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

export async function getOllamaCatalog(): Promise<OllamaCatalogEntry[]> {
  return request<OllamaCatalogEntry[]>('/llm-providers/model-catalog')
}

export async function pullOllamaModel(
  providerId: number,
  model: string,
): Promise<OllamaPullJob> {
  return request<OllamaPullJob>(`/llm-providers/${providerId}/models`, {
    method: 'POST',
    body: JSON.stringify({ model }),
  })
}

export async function deleteProviderModel(
  providerId: number,
  model: string,
): Promise<void> {
  await request(
    `/llm-providers/${providerId}/models?model=${encodeURIComponent(model)}`,
    { method: 'DELETE' },
  )
}

export async function streamOllamaPull(
  providerId: number,
  jobId: string,
  onEvent: (event: OllamaPullEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {}
  if (currentToken) {
    headers['Authorization'] = `Bearer ${currentToken}`
  }

  const response = await fetch(
    `${BASE}/llm-providers/${providerId}/models/pull/${encodeURIComponent(jobId)}/stream`,
    { headers, signal },
  )

  if (!response.ok || !response.body) {
    throw { message: 'Pull stream failed', status: response.status } as ApiError
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      const dataLine = frame.split('\n').find((line) => line.startsWith('data:'))
      if (!dataLine) {
        continue
      }
      const payload = dataLine.slice('data:'.length).trim()
      if (!payload) {
        continue
      }
      try {
        onEvent(JSON.parse(payload) as OllamaPullEvent)
      } catch {
        // Skip a malformed frame rather than killing the whole stream.
      }
    }
  }
}

export async function getTelegramBots(): Promise<TelegramBot[]> {
  return request<TelegramBot[]>('/telegram-bots')
}

export async function createTelegramBot(
  payload: TelegramBotCreatePayload,
): Promise<TelegramBot> {
  return request<TelegramBot>('/telegram-bots', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteTelegramBot(botId: number): Promise<void> {
  await request(`/telegram-bots/${botId}`, { method: 'DELETE' })
}

export async function getEmailAccounts(): Promise<EmailAccount[]> {
  return request<EmailAccount[]>('/email-accounts')
}

export async function createEmailAccount(
  payload: EmailAccountCreatePayload,
): Promise<EmailAccount> {
  return request<EmailAccount>('/email-accounts', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteEmailAccount(accountId: number): Promise<void> {
  await request(`/email-accounts/${accountId}`, { method: 'DELETE' })
}

export async function getPostgresConnections(): Promise<PostgresConnection[]> {
  return request<PostgresConnection[]>('/postgres-connections')
}

export async function createPostgresConnection(
  payload: PostgresConnectionCreatePayload,
): Promise<PostgresConnection> {
  return request<PostgresConnection>('/postgres-connections', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deletePostgresConnection(connectionId: number): Promise<void> {
  await request(`/postgres-connections/${connectionId}`, { method: 'DELETE' })
}

export async function getVectorCollections(): Promise<VectorCollection[]> {
  return request<VectorCollection[]>('/vector-collections')
}

export async function deleteVectorCollection(collection: string): Promise<void> {
  await request(`/vector-collections/${encodeURIComponent(collection)}`, {
    method: 'DELETE',
  })
}

export async function getVectorDocuments(
  collection: string,
): Promise<VectorDocument[]> {
  return request<VectorDocument[]>(
    `/vector-collections/${encodeURIComponent(collection)}/documents`,
  )
}

export async function deleteVectorDocument(
  collection: string,
  source: string,
): Promise<void> {
  await request(
    `/vector-collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(source)}`,
    { method: 'DELETE' },
  )
}

export async function uploadVectorDocument(
  collection: string,
  file: File,
  source?: string,
): Promise<VectorUploadJob> {
  const formData = new FormData()
  formData.append('file', file)
  if (source) {
    formData.append('source', source)
  }
  return request<VectorUploadJob>(
    `/vector-collections/${encodeURIComponent(collection)}/documents`,
    { method: 'POST', body: formData },
  )
}

export async function getVectorJobStatus(
  jobId: string,
): Promise<VectorJobStatus> {
  return request<VectorJobStatus>(
    `/vector-collections/jobs/${encodeURIComponent(jobId)}`,
  )
}
