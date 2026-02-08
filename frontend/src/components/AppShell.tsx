import type { ReactNode } from 'react'

import { UserMenu } from './UserMenu'

interface AppShellProps {
  email: string
  workflowName: string
  executionStatus: string | null
  error: string | null
  loading: boolean
  onRun: () => void
  onLogout: () => void
  onDeleteAccount: () => void
  children: ReactNode
}

export function AppShell({
  email,
  workflowName,
  executionStatus,
  error,
  loading,
  onRun,
  onLogout,
  onDeleteAccount,
  children,
}: AppShellProps) {
  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="pixel-topbar">
        <div className="flex items-center gap-4">
          <div className="font-pixel text-sm uppercase text-[var(--accent)]">
            Graph AI
          </div>
          <div className="text-xs text-[var(--muted)]">/ {workflowName}</div>
        </div>
        <div className="flex items-center gap-3">
          {executionStatus ? (
            <div className="pixel-pill">Status: {executionStatus}</div>
          ) : null}
          <button
            type="button"
            className="pixel-button small"
            onClick={onRun}
            disabled={loading}
          >
            {loading ? 'Running...' : 'Run'}
          </button>
          <UserMenu
            email={email}
            onLogout={onLogout}
            onDeleteAccount={onDeleteAccount}
          />
        </div>
      </header>
      {error ? <div className="pixel-banner">{error}</div> : null}
      <main className="grid h-[calc(100vh-84px)] grid-cols-[280px_1fr_320px] gap-3 px-4 pt-4 pb-4">
        {children}
      </main>
    </div>
  )
}
