import { useState } from 'react'

import type { Execution, ExecutionStatus } from '../lib/types'

interface ExecutionListProps {
  executions: Execution[]
  versionNumbers?: Record<number, number>
}

const STATUS_COLORS: Record<ExecutionStatus, string> = {
  created: 'text-[var(--muted)]',
  running: 'text-[var(--accent-2)]',
  success: 'text-[var(--accent)]',
  failed: 'text-[var(--danger)]',
}

function formatTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ExecutionList({
  executions,
  versionNumbers,
}: ExecutionListProps) {
  const [expandedExecutionId, setExpandedExecutionId] = useState<number | null>(null)

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
        <div
          key={execution.id}
          className={`pixel-card flex-col items-start gap-1 ${
            execution.output_data ? 'cursor-pointer' : ''
          }`}
          onClick={() => {
            if (!execution.output_data) {
              return
            }
            setExpandedExecutionId((current) =>
              current === execution.id ? null : execution.id,
            )
          }}
        >
          <div className="flex w-full items-center justify-between">
            <span className="flex items-center gap-2 text-xs text-[var(--muted)]">
              #{execution.id}
              {execution.version_id !== null &&
              versionNumbers?.[execution.version_id] !== undefined ? (
                <span className="pixel-pill text-[10px]">
                  v{versionNumbers[execution.version_id]}
                </span>
              ) : null}
            </span>
            <span className={`text-xs uppercase ${STATUS_COLORS[execution.status]}`}>
              {execution.status}
            </span>
          </div>
          <div className="text-xs text-[var(--muted)]">
            {formatTime(execution.started_at)}
            {execution.finished_at ? ` → ${formatTime(execution.finished_at)}` : ''}
          </div>
          {execution.output_data ? (
            <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
              {expandedExecutionId === execution.id
                ? 'Click to hide output'
                : 'Click to view output'}
            </div>
          ) : null}
          {execution.error ? (
            <div className="mt-1 w-full break-all text-xs text-[var(--danger)]">
              {execution.error}
            </div>
          ) : null}
          {execution.output_data && expandedExecutionId === execution.id ? (
            <pre className="hide-scrollbar mt-1 max-h-24 w-full overflow-auto text-xs text-[var(--text)] opacity-70">
              {JSON.stringify(execution.output_data, null, 2)}
            </pre>
          ) : null}
        </div>
      ))}
    </div>
  )
}
