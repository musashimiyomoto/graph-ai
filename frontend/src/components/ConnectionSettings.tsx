import { useState } from 'react'

import { useConnections } from '../hooks/useConnections'
import type {
  ApiError,
  Connection,
  ConnectionAuthType,
  ConnectionCreatePayload,
} from '../lib/types'

interface ConnectionSettingsProps {
  onError: (error: ApiError) => void
}

function formatTimestamp(value: string | null): string | null {
  return value ? new Date(value).toLocaleString() : null
}

function splitScopes(value: string): string[] {
  return [...new Set(value.split(/[\s,]+/).filter(Boolean))]
}

function connectionDetails(connection: Connection): string[] {
  const details: string[] = []
  const lastChecked = formatTimestamp(connection.last_checked_at)
  const lastUsed = formatTimestamp(connection.last_used_at)
  const expiresAt = formatTimestamp(connection.token_expires_at)
  if (lastChecked) {
    details.push(`Checked ${lastChecked}`)
  }
  if (lastUsed) {
    details.push(`Used ${lastUsed}`)
  }
  if (expiresAt) {
    details.push(`Token expires ${expiresAt}`)
  }
  return details
}

export function ConnectionSettings({ onError }: ConnectionSettingsProps) {
  const [name, setName] = useState('')
  const [provider, setProvider] = useState('')
  const [authType, setAuthType] = useState<ConnectionAuthType>('api_key')
  const [scopes, setScopes] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [headerName, setHeaderName] = useState('Authorization')
  const [prefix, setPrefix] = useState('Bearer')
  const [authorizationUrl, setAuthorizationUrl] = useState('')
  const [tokenUrl, setTokenUrl] = useState('')
  const [revocationUrl, setRevocationUrl] = useState('')
  const [healthUrl, setHealthUrl] = useState('')
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [busyConnectionId, setBusyConnectionId] = useState<number | null>(null)
  const {
    connections,
    loading,
    creating,
    operating,
    addConnection,
    beginOAuth,
    refreshOAuth,
    checkHealth,
    revoke,
    removeConnection,
    reload,
  } = useConnections({ onError })

  const providerValid = /^[a-z][a-z0-9_-]{0,63}$/.test(provider.trim())
  const apiKeyFieldsValid = authType === 'api_key' && Boolean(apiKey.trim())
  const oauthFieldsValid =
    authType === 'oauth2' &&
    Boolean(authorizationUrl.trim() && tokenUrl.trim() && clientId.trim())
  const formValid =
    Boolean(name.trim()) &&
    providerValid &&
    (authType === 'none' || apiKeyFieldsValid || oauthFieldsValid)

  function resetForm(): void {
    setName('')
    setProvider('')
    setScopes('')
    setApiKey('')
    setHeaderName('Authorization')
    setPrefix('Bearer')
    setAuthorizationUrl('')
    setTokenUrl('')
    setRevocationUrl('')
    setHealthUrl('')
    setClientId('')
    setClientSecret('')
  }

  async function handleCreate(): Promise<void> {
    const common: ConnectionCreatePayload = {
      name: name.trim(),
      provider: provider.trim(),
      auth_type: authType,
      scopes: splitScopes(scopes),
      health_url: healthUrl.trim() || undefined,
    }
    const payload: ConnectionCreatePayload =
      authType === 'none'
        ? common
        : authType === 'api_key'
        ? {
            ...common,
            api_key: apiKey.trim(),
            header_name: headerName.trim(),
            prefix: prefix.trim(),
          }
        : {
            ...common,
            authorization_url: authorizationUrl.trim(),
            token_url: tokenUrl.trim(),
            revocation_url: revocationUrl.trim() || undefined,
            client_id: clientId.trim(),
            client_secret: clientSecret || undefined,
          }
    if (await addConnection(payload)) {
      resetForm()
    }
  }

  async function handleOperation(
    connectionId: number,
    operation: () => Promise<boolean>,
  ): Promise<void> {
    setBusyConnectionId(connectionId)
    try {
      await operation()
    } finally {
      setBusyConnectionId(null)
    }
  }

  async function handleAuthorize(connectionId: number): Promise<void> {
    setBusyConnectionId(connectionId)
    try {
      const redirectUri = `${window.location.origin}/api/connections/oauth/callback`
      const started = await beginOAuth(connectionId, redirectUri)
      if (started) {
        window.open(started.authorization_url, '_blank', 'noopener,noreferrer')
      }
    } finally {
      setBusyConnectionId(null)
    }
  }

  async function handleDelete(connectionId: number): Promise<void> {
    await handleOperation(connectionId, () => removeConnection(connectionId))
    setConfirmDeleteId(null)
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="text-xs text-[var(--muted)]">
          Reusable encrypted credentials for provider adapters.
        </div>
        <button
          type="button"
          className="pixel-icon"
          disabled={loading}
          title="Refresh connections after completing OAuth"
          onClick={() => void reload()}
        >
          Refresh
        </button>
      </div>

      <div className="flex flex-col gap-3">
        {loading ? (
          <div className="text-xs text-[var(--muted)]">Loading connections...</div>
        ) : connections.length === 0 ? (
          <div className="text-xs text-[var(--muted)]">No unified connections yet.</div>
        ) : null}
        {connections.map((connection) => {
          const isBusy = operating && busyConnectionId === connection.id
          const isRevoked = connection.status === 'revoked'
          return (
            <div key={connection.id} className="pixel-card flex-col items-stretch gap-2">
              <div className="flex min-w-0 items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">{connection.name}</div>
                  <div className="text-xs text-[var(--muted)]">
                    {connection.provider} · {connection.auth_type} · {connection.status}
                  </div>
                </div>
                <div className="text-xs text-[var(--muted)]">
                  {connection.has_credentials ? 'Encrypted' : 'No credentials'}
                </div>
              </div>

              {connection.scopes.length > 0 ? (
                <div className="break-words text-xs text-[var(--muted)]">
                  Scopes: {connection.scopes.join(', ')}
                </div>
              ) : null}
              {connectionDetails(connection).map((detail) => (
                <div key={detail} className="text-xs text-[var(--muted)]">
                  {detail}
                </div>
              ))}
              {connection.last_error ? (
                <div className="break-words text-xs text-red-300">
                  {connection.last_error}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-2 pt-1">
                {connection.auth_type === 'oauth2' && !isRevoked ? (
                  <button
                    type="button"
                    className="pixel-icon"
                    disabled={operating}
                    onClick={() => void handleAuthorize(connection.id)}
                  >
                    Authorize
                  </button>
                ) : null}
                <button
                  type="button"
                  className="pixel-icon"
                  disabled={operating || isRevoked || !connection.has_credentials}
                  onClick={() =>
                    void handleOperation(connection.id, () =>
                      checkHealth(connection.id),
                    )
                  }
                >
                  Health
                </button>
                {connection.auth_type === 'oauth2' ? (
                  <button
                    type="button"
                    className="pixel-icon"
                    disabled={operating || isRevoked || !connection.has_credentials}
                    onClick={() =>
                      void handleOperation(connection.id, () =>
                        refreshOAuth(connection.id),
                      )
                    }
                  >
                    Refresh token
                  </button>
                ) : null}
                {!isRevoked ? (
                  <button
                    type="button"
                    className="pixel-icon danger"
                    disabled={operating}
                    onClick={() =>
                      void handleOperation(connection.id, () => revoke(connection.id))
                    }
                  >
                    Revoke
                  </button>
                ) : null}
                {confirmDeleteId === connection.id ? (
                  <>
                    <button
                      type="button"
                      className="pixel-icon danger"
                      disabled={operating}
                      title="Confirm delete"
                      onClick={() => void handleDelete(connection.id)}
                    >
                      {isBusy ? '...' : '✓'}
                    </button>
                    <button
                      type="button"
                      className="pixel-icon"
                      disabled={operating}
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
                    disabled={operating}
                    onClick={() => setConfirmDeleteId(connection.id)}
                  >
                    Del
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-6 border-t border-white/10 pt-4">
        <div className="mb-3 text-xs uppercase tracking-widest text-[var(--muted)]">
          Add connection
        </div>
        <div className="pixel-form-stack">
          <label className="pixel-label">
            Name
            <input
              className="pixel-input medium"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="GitHub production"
            />
          </label>
          <label className="pixel-label">
            Provider key
            <input
              className="pixel-input medium"
              value={provider}
              onChange={(event) => setProvider(event.target.value.toLowerCase())}
              placeholder="github"
            />
          </label>
          <label className="pixel-label">
            Authentication
            <select
              className="pixel-input compact"
              value={authType}
              onChange={(event) =>
                setAuthType(event.target.value as ConnectionAuthType)
              }
            >
              <option value="api_key">API key</option>
              <option value="oauth2">OAuth 2.0 + PKCE</option>
              <option value="none">No authentication</option>
            </select>
          </label>
          <label className="pixel-label">
            Scopes (space or comma separated)
            <input
              className="pixel-input medium"
              value={scopes}
              onChange={(event) => setScopes(event.target.value)}
              placeholder="repo, read:user"
            />
          </label>

          {authType === 'api_key' ? (
            <>
              <label className="pixel-label">
                API key
                <input
                  className="pixel-input medium"
                  type="password"
                  value={apiKey}
                  autoComplete="off"
                  onChange={(event) => setApiKey(event.target.value)}
                />
              </label>
              <label className="pixel-label">
                Header name
                <input
                  className="pixel-input medium"
                  value={headerName}
                  onChange={(event) => setHeaderName(event.target.value)}
                />
              </label>
              <label className="pixel-label">
                Value prefix
                <input
                  className="pixel-input compact"
                  value={prefix}
                  onChange={(event) => setPrefix(event.target.value)}
                  placeholder="Bearer"
                />
              </label>
            </>
          ) : authType === 'oauth2' ? (
            <>
              <label className="pixel-label">
                Authorization URL
                <input
                  className="pixel-input medium"
                  type="url"
                  value={authorizationUrl}
                  onChange={(event) => setAuthorizationUrl(event.target.value)}
                  placeholder="https://provider.example/oauth/authorize"
                />
              </label>
              <label className="pixel-label">
                Token URL
                <input
                  className="pixel-input medium"
                  type="url"
                  value={tokenUrl}
                  onChange={(event) => setTokenUrl(event.target.value)}
                  placeholder="https://provider.example/oauth/token"
                />
              </label>
              <label className="pixel-label">
                Revocation URL (optional)
                <input
                  className="pixel-input"
                  type="url"
                  value={revocationUrl}
                  onChange={(event) => setRevocationUrl(event.target.value)}
                />
              </label>
              <label className="pixel-label">
                Client ID
                <input
                  className="pixel-input"
                  value={clientId}
                  onChange={(event) => setClientId(event.target.value)}
                />
              </label>
              <label className="pixel-label">
                Client secret (optional)
                <input
                  className="pixel-input"
                  type="password"
                  value={clientSecret}
                  autoComplete="off"
                  onChange={(event) => setClientSecret(event.target.value)}
                />
              </label>
            </>
          ) : null}

          <label className="pixel-label">
            Health URL (optional)
            <input
              className="pixel-input"
              type="url"
              value={healthUrl}
              onChange={(event) => setHealthUrl(event.target.value)}
              placeholder="https://api.provider.example/user"
            />
          </label>
          <button
            type="button"
            className="pixel-button small"
            disabled={creating || !formValid}
            onClick={() => void handleCreate()}
          >
            {creating ? 'Saving...' : 'Add Connection'}
          </button>
        </div>
      </div>
    </div>
  )
}
