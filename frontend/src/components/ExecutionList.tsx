import type { Execution, ExecutionStatus } from '../lib/types'

interface ExecutionListProps {
  executions: Execution[]
  loading: boolean
}

const STATUS_COLORS: Record<ExecutionStatus, string> = {
  created: 'text-[var(--muted)]',
  running: 'text-[var(--accent-2)]',
  success: 'text-[var(--accent)]',
  failed: 'text-[var(--danger)]',
}

function formatTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ExecutionList({ executions, loading }: ExecutionListProps) {
  if (loading) {
    return (
      <div className="text-xs text-[var(--muted)]">Loading executions...</div>
    )
  }

  if (executions.length === 0) {
    return (
      <div className="text-xs text-[var(--muted)]">
        No executions yet. Click Run to start one.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {executions.map((execution) => (
        <div key={execution.id} className="pixel-card flex-col items-start gap-1">
          <div className="flex w-full items-center justify-between">
            <span className="text-xs text-[var(--muted)]">
              #{execution.id}
            </span>
            <span className={`text-xs uppercase ${STATUS_COLORS[execution.status]}`}>
              {execution.status}
            </span>
          </div>
          <div className="text-xs text-[var(--muted)]">
            {formatTime(execution.started_at)}
            {execution.finished_at ? ` → ${formatTime(execution.finished_at)}` : ''}
          </div>
          {execution.error ? (
            <div className="mt-1 w-full break-all text-xs text-[var(--danger)]">
              {execution.error}
            </div>
          ) : null}
          {execution.output_data ? (
            <pre className="mt-1 max-h-24 w-full overflow-auto text-xs text-[var(--text)] opacity-70">
              {JSON.stringify(execution.output_data, null, 2)}
            </pre>
          ) : null}
        </div>
      ))}
    </div>
  )
}
