import { type ReactNode, useEffect, useState } from 'react'

import type { ApiError } from '../lib/types'
import { SettingsModal } from './SettingsModal'
import { UserMenu } from './UserMenu'

// Auto-dismiss the error banner after this long so a transient failure
// doesn't linger on screen forever if the user doesn't notice it.
const ERROR_BANNER_TIMEOUT_MS = 8000

interface AppShellProps {
  email: string
  workflowName: string
  error: string | null
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onAutoLayout: () => void
  onOpenTestRuns: () => void
  onOpenActivityLog: () => void
  onDismissError: () => void
  onLogout: () => void
  onDeleteAccount: () => void
  onError: (err: ApiError) => void
  children: ReactNode
}

export function AppShell({
  email,
  workflowName,
  error,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onAutoLayout,
  onOpenTestRuns,
  onOpenActivityLog,
  onDismissError,
  onLogout,
  onDeleteAccount,
  onError,
  children,
}: AppShellProps) {
  const [showSettings, setShowSettings] = useState(false)

  useEffect(() => {
    if (!error) {
      return
    }
    const timer = window.setTimeout(onDismissError, ERROR_BANNER_TIMEOUT_MS)
    return () => window.clearTimeout(timer)
  }, [error, onDismissError])

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="pixel-topbar flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-4">
          <div className="font-pixel text-sm uppercase text-[var(--accent)]">
            Graph AI
          </div>
          <div className="truncate text-xs text-[var(--muted)]">/ {workflowName}</div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="pixel-icon"
            disabled={!canUndo}
            title="Undo (Ctrl+Z)"
            onClick={onUndo}
          >
            Undo
          </button>
          <button
            type="button"
            className="pixel-icon"
            disabled={!canRedo}
            title="Redo (Ctrl+Shift+Z)"
            onClick={onRedo}
          >
            Redo
          </button>
          <button
            type="button"
            className="pixel-icon"
            title="Auto-layout"
            onClick={onAutoLayout}
          >
            Auto-layout
          </button>
          <button type="button" className="pixel-icon" onClick={onOpenTestRuns}>
            Test Runs
          </button>
          <button type="button" className="pixel-icon" onClick={onOpenActivityLog}>
            Activity Log
          </button>
          <button
            type="button"
            className="pixel-icon"
            onClick={() => setShowSettings(true)}
          >
            Settings
          </button>
          <UserMenu
            email={email}
            onLogout={onLogout}
            onDeleteAccount={onDeleteAccount}
          />
        </div>
      </header>
      {showSettings ? (
        <SettingsModal
          onClose={() => setShowSettings(false)}
          onError={onError}
        />
      ) : null}
      {error ? (
        <div className="pixel-banner flex items-center justify-between gap-3">
          <span>{error}</span>
          <button
            type="button"
            className="pixel-icon"
            onClick={onDismissError}
          >
            ✕
          </button>
        </div>
      ) : null}
      <main className="grid h-[calc(100vh-84px)] grid-cols-[280px_1fr_320px] gap-3 px-4 pt-4 pb-4">
        {children}
      </main>
    </div>
  )
}
