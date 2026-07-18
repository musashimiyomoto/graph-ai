import { useState } from 'react'

import { usePostgresConnections } from '../hooks/usePostgresConnections'
import type { ApiError } from '../lib/types'

interface PostgresConnectionSettingsProps {
  onError: (error: ApiError) => void
}

export function PostgresConnectionSettings({
  onError,
}: PostgresConnectionSettingsProps) {
  const [name, setName] = useState('')
  const [dsn, setDsn] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const { connections, loading, creating, createConnection, removeConnection } =
    usePostgresConnections({ onError })

  async function handleCreate(): Promise<void> {
    const created = await createConnection({ name: name.trim(), dsn: dsn.trim() })
    if (created) {
      setName('')
      setDsn('')
    }
  }

  async function handleDelete(connectionId: number): Promise<void> {
    if (await removeConnection(connectionId)) {
      setConfirmDeleteId(null)
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-3">
        {loading ? (
          <div className="text-xs text-[var(--muted)]">Loading connections...</div>
        ) : connections.length === 0 ? (
          <div className="text-xs text-[var(--muted)]">No PostgreSQL connections yet.</div>
        ) : null}
        {connections.map((connection) => (
          <div key={connection.id} className="pixel-card">
            <div className="min-w-0 flex-1 truncate text-sm">{connection.name}</div>
            {confirmDeleteId === connection.id ? (
              <>
                <button
                  type="button"
                  className="pixel-icon danger"
                  title="Confirm delete"
                  onClick={() => void handleDelete(connection.id)}
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
                onClick={() => setConfirmDeleteId(connection.id)}
              >
                Del
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 border-t border-white/10 pt-4">
        <div className="mb-3 text-xs uppercase tracking-widest text-[var(--muted)]">
          Add connection
        </div>
        <div className="flex flex-col gap-3">
          <label className="pixel-label">
            Name
            <input
              className="pixel-input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Analytics database"
            />
          </label>
          <label className="pixel-label">
            PostgreSQL DSN
            <input
              className="pixel-input"
              type="password"
              value={dsn}
              autoComplete="off"
              onChange={(event) => setDsn(event.target.value)}
              placeholder="postgresql://user:password@host:5432/database"
            />
          </label>
          <button
            type="button"
            className="pixel-button small"
            disabled={creating || !name.trim() || !dsn.trim()}
            onClick={() => void handleCreate()}
          >
            {creating ? 'Saving...' : 'Add Connection'}
          </button>
        </div>
      </div>
    </div>
  )
}
