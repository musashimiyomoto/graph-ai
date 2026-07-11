import type { ExecutionStatus } from './types'

export const STATUS_COLORS: Record<ExecutionStatus, string> = {
  created: 'text-[var(--muted)]',
  running: 'text-[var(--accent-2)]',
  success: 'text-[var(--accent)]',
  failed: 'text-[var(--danger)]',
}

// Background-color variant of STATUS_COLORS for dot/badge indicators.
export const STATUS_DOT_COLORS: Record<ExecutionStatus, string> = {
  created: 'bg-[var(--muted)]',
  running: 'bg-[var(--accent-2)]',
  success: 'bg-[var(--accent)]',
  failed: 'bg-[var(--danger)]',
}

export function formatTime(iso: string): string {
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

export function formatDuration(
  startedAt: string,
  finishedAt: string | null,
): string | null {
  if (!finishedAt) {
    return null
  }
  const start = new Date(startedAt).getTime()
  const finish = new Date(finishedAt).getTime()
  if (Number.isNaN(start) || Number.isNaN(finish) || finish < start) {
    return null
  }
  const ms = finish - start
  if (ms < 1000) {
    return `${ms}ms`
  }
  return `${(ms / 1000).toFixed(1)}s`
}
