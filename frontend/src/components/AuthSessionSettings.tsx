import { useAuthSessions } from '../hooks/useAuthSessions'
import type { ApiError } from '../lib/types'

export function AuthSessionSettings({
  onError,
}: {
  onError: (error: ApiError) => void
}) {
  const { sessions, loading, revoking, revoke } = useAuthSessions(onError)

  return (
    <div className="flex flex-col gap-3">
      {loading ? (
        <div className="text-xs text-[var(--muted)]">Loading sessions...</div>
      ) : null}
      {sessions.map((session) => (
        <div key={session.id} className="pixel-card">
          <div className="min-w-0 flex-1">
            <div className="text-sm">
              {session.current ? 'Current session' : session.user_agent || 'Unknown client'}
            </div>
            <div className="text-xs text-[var(--muted)]">
              Last used {new Date(session.last_used_at).toLocaleString()}
              {session.ip_address ? ` · ${session.ip_address}` : ''}
            </div>
          </div>
          <button
            type="button"
            className="pixel-button danger small"
            disabled={revoking}
            onClick={() => void revoke(session.id)}
          >
            Revoke
          </button>
        </div>
      ))}
    </div>
  )
}
