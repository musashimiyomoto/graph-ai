import { useState } from 'react'

import { useMCPRegistry } from '../hooks/useMCPRegistry'
import { useMCPServers } from '../hooks/useMCPServers'
import { resolveRegistryConfiguration } from '../lib/mcpRegistry'
import type { ApiError, MCPRegistryServer } from '../lib/types'

interface MCPServerSettingsProps {
  onError: (error: ApiError) => void
}

export function MCPServerSettings({ onError }: MCPServerSettingsProps) {
  const [tab, setTab] = useState<'saved' | 'catalog'>('saved')
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [headersText, setHeadersText] = useState('{}')
  const [headersError, setHeadersError] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [catalogServer, setCatalogServer] = useState<MCPRegistryServer | null>(null)
  const [catalogValues, setCatalogValues] = useState<Record<string, string>>({})
  const { servers, loading, creating, createServer, removeServer } = useMCPServers({
    onError,
  })
  const {
    servers: catalog,
    loading: catalogLoading,
    error: catalogError,
  } = useMCPRegistry(search, tab === 'catalog')

  function configureFromCatalog(server: MCPRegistryServer) {
    setCatalogServer(server)
    setCatalogValues(
      Object.fromEntries(
        server.inputs.map((input) => [input.key, input.default ?? '']),
      ),
    )
    setName(server.name)
    setUrl(server.url_template)
    setHeadersText(JSON.stringify(server.header_templates, null, 2))
    setHeadersError(null)
    setTab('saved')
  }

  function clearCatalogConfiguration() {
    setCatalogServer(null)
    setCatalogValues({})
    setUrl('')
    setHeadersText('{}')
  }

  async function handleCreate() {
    let resolvedUrl = url.trim()
    let headers: Record<string, string>
    if (catalogServer) {
      const missing = catalogServer.inputs.find(
        (input) => input.required && !catalogValues[input.key]?.trim(),
      )
      if (missing) {
        setHeadersError(`Configuration value "${missing.key}" is required.`)
        return
      }
      const resolved = resolveRegistryConfiguration(catalogServer, catalogValues)
      resolvedUrl = resolved.url
      headers = resolved.headers
    } else {
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
    }
    setHeadersError(null)
    const created = await createServer({
      name: name.trim(),
      url: resolvedUrl,
      headers,
    })
    if (created) {
      setName('')
      clearCatalogConfiguration()
    }
  }

  return (
    <div>
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          className={`pixel-tab ${tab === 'saved' ? 'is-active' : ''}`}
          onClick={() => setTab('saved')}
        >
          Saved
        </button>
        <button
          type="button"
          className={`pixel-tab ${tab === 'catalog' ? 'is-active' : ''}`}
          onClick={() => setTab('catalog')}
        >
          Catalog
        </button>
      </div>

      {tab === 'catalog' ? (
        <div className="flex flex-col gap-3">
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              setSearch(searchInput.trim())
            }}
          >
            <input
              className="pixel-input min-w-0 flex-1"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search official MCP Registry"
            />
            <button type="submit" className="pixel-button small">
              Search
            </button>
          </form>
          {catalogLoading ? (
            <div className="text-xs text-[var(--muted)]">Loading catalog...</div>
          ) : catalogError ? (
            <div className="text-xs text-[var(--danger)]">
              Official MCP Registry is currently unavailable.
            </div>
          ) : catalog.length === 0 ? (
            <div className="text-xs text-[var(--muted)]">
              No remote Streamable HTTP servers found.
            </div>
          ) : (
            catalog.map((server) => (
              <div key={`${server.registry_name}:${server.version}`} className="pixel-card">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">
                    {server.name} <span className="text-[var(--muted)]">v{server.version}</span>
                  </div>
                  {server.description ? (
                    <div className="mt-1 line-clamp-2 text-xs text-[var(--muted)]">
                      {server.description}
                    </div>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="pixel-button small"
                  onClick={() => configureFromCatalog(server)}
                >
                  Configure
                </button>
              </div>
            ))
          )}
        </div>
      ) : (
        <>
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
                      onClick={() =>
                        void removeServer(server.id).then(() => setConfirmDeleteId(null))
                      }
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
            <div className="mb-3 flex items-center justify-between">
              <div className="text-xs uppercase tracking-widest text-[var(--muted)]">
                Add Streamable HTTP server
              </div>
              {catalogServer ? (
                <button
                  type="button"
                  className="pixel-button ghost small"
                  onClick={clearCatalogConfiguration}
                >
                  Clear catalog preset
                </button>
              ) : null}
            </div>
            <div className="pixel-form-stack">
              {catalogServer ? (
                <div className="text-xs text-[var(--accent-2)]">
                  Configuring {catalogServer.registry_name} v{catalogServer.version}
                </div>
              ) : null}
              <label className="pixel-label">
                Name
                <input
                  className="pixel-input medium"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Company tools"
                />
              </label>
              {catalogServer
                ? catalogServer.inputs.map((input) => (
                    <label key={input.key} className="pixel-label">
                      {input.key}
                      <input
                        className="pixel-input"
                        type={input.secret ? 'password' : 'text'}
                        autoComplete="off"
                        value={catalogValues[input.key] ?? ''}
                        placeholder={input.placeholder ?? ''}
                        onChange={(event) =>
                          setCatalogValues((previous) => ({
                            ...previous,
                            [input.key]: event.target.value,
                          }))
                        }
                      />
                      {input.description ? (
                        <span className="text-xs text-[var(--muted)]">
                          {input.description}
                        </span>
                      ) : null}
                    </label>
                  ))
                : (
                    <>
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
                      </label>
                    </>
                  )}
              {headersError ? (
                <span className="text-xs text-[var(--danger)]">{headersError}</span>
              ) : (
                <span className="text-xs text-[var(--muted)]">
                  Headers and catalog secrets are encrypted and never returned by the API.
                </span>
              )}
              <button
                type="button"
                className="pixel-button small"
                disabled={creating || !name.trim() || (!catalogServer && !url.trim())}
                onClick={() => void handleCreate()}
              >
                {creating ? 'Saving...' : 'Add MCP Server'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
