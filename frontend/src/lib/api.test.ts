import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  cancelExecution,
  getWorkflows,
  login,
  publicWebhookUrl,
  setToken,
  webChatEmbedSnippet,
} from './api'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('api request()', () => {
  beforeEach(() => {
    setToken(null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setToken(null)
  })

  it('returns the parsed JSON body on success', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([{ id: 1 }]))
    vi.stubGlobal('fetch', fetchMock)

    const result = await getWorkflows()

    expect(result).toEqual([{ id: 1 }])
    expect(fetchMock).toHaveBeenCalledWith('/api/workflows', expect.anything())
  })

  it('normalizes a network-level failure into an ApiError shape', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('boom')))

    await expect(getWorkflows()).rejects.toEqual({
      message: 'Network error — check your connection.',
      status: 0,
    })
  })

  it('throws the server detail message and status for a non-ok response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: 'Nope' }, { status: 403 }),
      ),
    )

    await expect(getWorkflows()).rejects.toEqual({
      message: 'Nope',
      status: 403,
    })
  })

  it('falls back to statusText when the error body has no detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('{}', { status: 500, statusText: 'Server Error' }),
      ),
    )

    await expect(getWorkflows()).rejects.toEqual({
      message: 'Server Error',
      status: 500,
    })
  })

  it('sets a JSON content type and forwards the request body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ access_token: 't' }))
    vi.stubGlobal('fetch', fetchMock)

    await login('a@example.com', 'secret')

    const [, options] = fetchMock.mock.calls[0]
    expect(options.method).toBe('POST')
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(options.body as string)).toEqual({
      email: 'a@example.com',
      password: 'secret',
    })
  })

  it('injects the bearer token once set', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', fetchMock)
    setToken('abc123')

    await getWorkflows()

    const [, options] = fetchMock.mock.calls[0]
    expect(options.headers['Authorization']).toBe('Bearer abc123')
  })

  it('cancels an execution with a POST request', async () => {
    const execution = { id: 42, status: 'cancelled' }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(execution))
    vi.stubGlobal('fetch', fetchMock)

    await expect(cancelExecution(42)).resolves.toEqual(execution)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/executions/42/cancel',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

describe('publicWebhookUrl()', () => {
  it('builds an absolute URL through the public API prefix', () => {
    expect(publicWebhookUrl('/webhooks/12.signature')).toBe(
      `${window.location.origin}/api/webhooks/12.signature`,
    )
  })
})

describe('webChatEmbedSnippet()', () => {
  it('builds a drop-in loader with the signed public endpoint', () => {
    expect(webChatEmbedSnippet('/web-chat/12.signature')).toBe(
      `<script src="${window.location.origin}/graph-ai-chat.js" ` +
        `data-endpoint="${window.location.origin}/api/web-chat/12.signature" async></script>`,
    )
  })
})
