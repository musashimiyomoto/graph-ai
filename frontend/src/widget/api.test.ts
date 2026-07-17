import { describe, expect, it, vi } from 'vitest'

import { createWebChatExecution, streamWebChatExecution } from './api'

describe('web-chat public API', () => {
  it('creates an execution without an authorization header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 9, status: 'created' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await createWebChatExecution('https://graph.example/api/web-chat/token', 'Hello')

    expect(fetchMock).toHaveBeenCalledWith(
      'https://graph.example/api/web-chat/token/executions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ value: 'Hello' }),
      }),
    )
    const options = fetchMock.mock.calls[0][1] as RequestInit
    expect((options.headers as Record<string, string>)['Authorization']).toBeUndefined()
  })

  it('parses SSE frames from the public stream', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"token","node_id":3,"delta":"Hi"}\n\n'),
        )
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 200 })))
    const onEvent = vi.fn()

    await streamWebChatExecution(
      'https://graph.example/api/web-chat/token',
      9,
      onEvent,
      new AbortController().signal,
    )

    expect(onEvent).toHaveBeenCalledWith({
      type: 'token',
      node_id: 3,
      delta: 'Hi',
    })
  })
})
