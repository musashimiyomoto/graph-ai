import type { ApiError, Execution, ExecutionStreamEvent } from '../lib/types'

async function publicRequest<T>(url: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...((options.headers as Record<string, string>) ?? {}),
      },
    })
  } catch {
    throw { message: 'Connection failed.', status: 0 } as ApiError
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw {
      message: (body as { detail?: string }).detail ?? 'Request failed.',
      status: response.status,
    } as ApiError
  }
  return (await response.json()) as T
}

export async function createWebChatExecution(
  endpoint: string,
  value: string,
  eventId: string,
  conversationId: string,
): Promise<Execution> {
  return publicRequest<Execution>(`${endpoint}/executions`, {
    method: 'POST',
    body: JSON.stringify({
      value,
      event_id: eventId,
      conversation_id: conversationId,
      locale: navigator.language || null,
    }),
  })
}

export async function getWebChatExecution(
  endpoint: string,
  executionId: number,
): Promise<Execution> {
  return publicRequest<Execution>(`${endpoint}/executions/${executionId}`)
}

export async function streamWebChatExecution(
  endpoint: string,
  executionId: number,
  onEvent: (event: ExecutionStreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${endpoint}/executions/${executionId}/stream`, {
    signal,
  })
  if (!response.ok || !response.body) {
    throw { message: 'Stream failed.', status: response.status } as ApiError
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const line = frame.split('\n').find((item) => item.startsWith('data:'))
      if (!line) continue
      try {
        onEvent(JSON.parse(line.slice('data:'.length).trim()) as ExecutionStreamEvent)
      } catch {
        // Ignore one malformed frame and keep the public stream alive.
      }
    }
  }
}
