import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  approveExecution,
  cancelExecution,
  checkConnectionHealth,
  createConnection,
  getChannelCatalog,
  getConnections,
  getWorkflows,
  login,
  publicWebhookUrl,
  refreshConnection,
  revokeConnection,
  setToken,
  startConnectionOAuth,
  updateVectorSyncState,
  uploadVectorDocument,
  rejectExecution,
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

  it('loads the plugin-driven channel catalog', async () => {
    const catalog = [{ source: 'telegram', label: 'Telegram' }]
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(catalog))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getChannelCatalog()).resolves.toEqual(catalog)
    expect(fetchMock).toHaveBeenCalledWith('/api/channels/catalog', expect.anything())
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

  it.each([
    ['approve', approveExecution],
    ['reject', rejectExecution],
  ])('submits an approval decision with POST /%s', async (action, decide) => {
    const execution = { id: 42, status: action === 'approve' ? 'created' : 'rejected' }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(execution))
    vi.stubGlobal('fetch', fetchMock)

    await expect(decide(42)).resolves.toEqual(execution)
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/executions/42/${action}`,
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('creates and lists unified connections without changing the payload', async () => {
    const connection = { id: 7, name: 'GitHub', auth_type: 'oauth2' }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(connection))
      .mockResolvedValueOnce(jsonResponse([connection]))
    vi.stubGlobal('fetch', fetchMock)
    const payload = {
      name: 'GitHub',
      provider: 'github',
      auth_type: 'oauth2' as const,
      authorization_url: 'https://github.com/login/oauth/authorize',
      token_url: 'https://github.com/login/oauth/access_token',
      client_id: 'client-id',
      scopes: ['repo', 'read:user'],
    }

    await expect(createConnection(payload)).resolves.toEqual(connection)
    await expect(getConnections()).resolves.toEqual([connection])

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/connections',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/connections',
      expect.anything(),
    )
  })

  it('starts OAuth with the public callback URL', async () => {
    const started = {
      authorization_url: 'https://provider.example/oauth?state=opaque',
      expires_at: '2026-07-25T12:10:00Z',
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(started))
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      startConnectionOAuth(7, 'https://app.example/api/connections/oauth/callback'),
    ).resolves.toEqual(started)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/connections/7/oauth/start',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          redirect_uri: 'https://app.example/api/connections/oauth/callback',
        }),
      }),
    )
  })

  it.each([
    ['refresh', refreshConnection],
    ['health', checkConnectionHealth],
    ['revoke', revokeConnection],
  ])('runs the connection %s lifecycle action', async (action, operation) => {
    const connection = { id: 7, status: 'active' }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(connection))
    vi.stubGlobal('fetch', fetchMock)

    await expect(operation(7)).resolves.toEqual(connection)
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/connections/7/${action}`,
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('serializes knowledge source revision, ACL, and retention metadata', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ job_id: 'knowledge:1:job', source: 'page' }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await uploadVectorDocument(
      'research',
      new File(['hello'], 'page.txt', { type: 'text/plain' }),
      'page',
      {
        source_type: 'notion',
        external_id: 'page-42',
        revision: 'etag-v1',
        acl_visibility: 'shared',
        acl_readers: ['team:research'],
        retention_days: 30,
        metadata: { space: 'engineering' },
      },
    )

    const [, options] = fetchMock.mock.calls[0]
    const body = options.body as FormData
    expect(body.get('source_type')).toBe('notion')
    expect(body.get('revision')).toBe('etag-v1')
    expect(body.get('acl_readers')).toBe('team:research')
    expect(body.get('retention_days')).toBe('30')
    expect(body.get('metadata_json')).toBe('{"space":"engineering"}')
    expect(options.headers['Content-Type']).toBeUndefined()
  })

  it('checkpoints a knowledge collection sync cursor', async () => {
    const collection = { name: 'research', sync_cursor: 'next-page' }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(collection))
    vi.stubGlobal('fetch', fetchMock)

    await expect(updateVectorSyncState('research', 'next-page')).resolves.toEqual(
      collection,
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/vector-collections/research/sync-state',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ sync_cursor: 'next-page' }),
      }),
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
