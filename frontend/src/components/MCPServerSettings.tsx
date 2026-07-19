import { useState } from 'react'

import { useMCPServers } from '../hooks/useMCPServers'
import type { ApiError } from '../lib/types'

interface MCPServerSettingsProps {
  onError: (error: ApiError) => void
}

export function MCPServerSettings({ onError }: MCPServerSettingsProps) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [headersText, setHeadersText] = useState('{}')
  const [headersError, setHeadersError] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const { servers, loading, creating, createServer, removeServer } = useMCPServers({
    onError,
  })

  async function handleCreate() {
    let headers: Record<string, string>
    try {
      const parsed = JSON.parse(headersText) as unknown
      if (
        !parsed ||
        typeof parsed !== 'object' ||
        Array.isArray(parsed) ||
        !Object.values(parsed).every((value) => typeof value === 'string')
      ) {
        throw new Error('invalid headers')
      }
      headers = parsed as Record<string, string>
    } catch {
      setHeadersError('Headers must be a JSON object of strings.')
      return
    }
    setHeadersError(null)
    const created = await createServer({
      name: name.trim(),
      url: url.trim(),
      headers,
    })
    if (created) {
      setName('')
      setUrl('')
      setHeadersText('{}')
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-3">
        {loading ? (
          <div className="text-xs text-[var(--muted)]">Loading MCP servers...</div>
        ) : servers.length === 0 ? (
          <div className="text-xs text-[var(--muted)]">No MCP servers yet.</div>
        ) : null}
        {servers.map((server) => (
          <div key={server.id} className="pixel-card">
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm">{server.name}</div>
              <div className="truncate text-xs text-[var(--muted)]">{server.url}</div>
            </div>
            {confirmDeleteId === server.id ? (
              <>
                <button
                  type="button"
                  className="pixel-icon danger"
                  title="Confirm delete"
                  onClick={() => void removeServer(server.id).then(() => setConfirmDeleteId(null))}
                >
                  ✓
                </button>
                <button
                  type="button"
                  className="pixel-icon"
                  title="Cancel"
                  onClick={() => setConfirmDeleteId(null)}
                >
                  ✕
                </button>
              </>
            ) : (
              <button
                type="button"
                className="pixel-icon danger"
                onClick={() => setConfirmDeleteId(server.id)}
              >
                Del
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 border-t border-white/10 pt-4">
        <div className="mb-3 text-xs uppercase tracking-widest text-[var(--muted)]">
          Add Streamable HTTP server
        </div>
        <div className="flex flex-col gap-3">
          <label className="pixel-label">
            Name
            <input
              className="pixel-input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Company tools"
            />
          </label>
          <label className="pixel-label">
            MCP URL
            <input
              className="pixel-input"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://mcp.example.com/mcp"
            />
          </label>
          <label className="pixel-label">
            HTTP headers (JSON)
            <textarea
              className="pixel-textarea"
              value={headersText}
              onChange={(event) => setHeadersText(event.target.value)}
              placeholder='{"Authorization":"Bearer ..."}'
            />
            {headersError ? (
              <span className="text-xs text-[var(--danger)]">{headersError}</span>
            ) : (
              <span className="text-xs text-[var(--muted)]">
                Headers are encrypted and never returned by the API.
              </span>
            )}
          </label>
          <button
            type="button"
            className="pixel-button small"
            disabled={creating || !name.trim() || !url.trim()}
            onClick={() => void handleCreate()}
          >
            {creating ? 'Saving...' : 'Add MCP Server'}
          </button>
        </div>
      </div>
    </div>
  )
}
