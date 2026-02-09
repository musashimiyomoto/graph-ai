import { type ReactNode, useState } from 'react'

import type { ApiError, Execution } from '../lib/types'
import { ExecutionHistory } from './ExecutionHistory'
import { ProviderManager } from './ProviderManager'
import { RunInputModal } from './RunInputModal'
import { UserMenu } from './UserMenu'

interface AppShellProps {
  email: string
  workflowName: string
  executionStatus: string | null
  error: string | null
  loading: boolean
  executions: Execution[]
  executionsLoading: boolean
  runInput: string
  onRun: (input: string) => void
  onLogout: () => void
  onDeleteAccount: () => void
  onError: (err: ApiError) => void
  children: ReactNode
}

export function AppShell({
  email,
  workflowName,
  executionStatus,
  error,
  loading,
  executions,
  executionsLoading,
  runInput,
  onRun,
  onLogout,
  onDeleteAccount,
  onError,
  children,
}: AppShellProps) {
  const [showProviders, setShowProviders] = useState(false)
  const [showExecutions, setShowExecutions] = useState(false)
  const [showRunInput, setShowRunInput] = useState(false)

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
            className="pixel-button ghost small"
            onClick={() => setShowProviders(true)}
          >
            Providers
          </button>
          <button
            type="button"
            className="pixel-button ghost small"
            onClick={() => setShowExecutions(true)}
          >
            Executions
          </button>
          <button
            type="button"
            className="pixel-button small"
            onClick={() => setShowRunInput(true)}
          >
            Run
          </button>
          <UserMenu
            email={email}
            onLogout={onLogout}
            onDeleteAccount={onDeleteAccount}
          />
        </div>
      </header>
      {showProviders ? (
        <ProviderManager
          onClose={() => setShowProviders(false)}
          onError={onError}
        />
      ) : null}
      {showRunInput ? (
        <RunInputModal
          initialValue={runInput}
          loading={loading}
          onRun={(input) => {
            onRun(input)
            setShowRunInput(false)
          }}
          onClose={() => setShowRunInput(false)}
        />
      ) : null}
      {showExecutions ? (
        <ExecutionHistory
          executions={executions}
          loading={executionsLoading}
          onClose={() => setShowExecutions(false)}
        />
      ) : null}
      {error ? <div className="pixel-banner">{error}</div> : null}
      <main className="grid h-[calc(100vh-84px)] grid-cols-[280px_1fr_320px] gap-3 px-4 pt-4 pb-4">
        {children}
      </main>
    </div>
  )
}
