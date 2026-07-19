import { useEffect, useMemo, useRef, useState } from 'react'

import { getWorkflowVersions } from '../lib/api'
import type { LiveTokens } from '../hooks/useExecutions'
import { formatTime, STATUS_COLORS } from '../lib/executionFormat'
import type {
  Execution,
  ExecutionStatus,
  NodeMeta,
  RunInputPayload,
} from '../lib/types'
import { ACTIVE_STATUSES } from '../lib/types'
import { ExecutionDetails } from './ExecutionDetails'

interface ChatPanelProps {
  workflowName: string
  hasWorkflow: boolean
  activeWorkflowId: number | null
  executions: Execution[]
  liveTokens: LiveTokens
  lastExecution: Execution | null
  runEnabled: boolean
  runDisabledReason: string | null
  loading: boolean
  cancelling: boolean
  nodeMetaByNodeId: Map<number, NodeMeta>
  onRun: (input: RunInputPayload) => void
  onCancel: () => void
}

interface ChatTurn {
  id: number
  execution: Execution
  status: ExecutionStatus
  input: string
  output: string
  error: string | null
  isActive: boolean
}

// The Output node is the only one whose stream is user-facing; the other
// nodes' tokens are intermediate work product and would otherwise show up
// concatenated into one garbled blob.
function findOutputNodeId(nodeMetaByNodeId: Map<number, NodeMeta>): number | null {
  for (const [nodeId, meta] of nodeMetaByNodeId) {
    if (meta.type === 'output') {
      return nodeId
    }
  }
  return null
}

function liveOutputText(liveTokens: LiveTokens, outputNodeId: number | null): string {
  if (outputNodeId === null) {
    return ''
  }
  return liveTokens[outputNodeId] ?? ''
}

// Distance (px) from the bottom of the scroll container within which new
// output still auto-scrolls into view; further away, the user is presumed
// to be reading earlier history and shouldn't get yanked back down.
const NEAR_BOTTOM_THRESHOLD_PX = 120

function buildTurns(
  executions: Execution[],
  activeId: number | null,
  liveText: string,
): ChatTurn[] {
  return [...executions]
    .sort((first, second) => first.id - second.id)
    .map((execution) => {
      const isActive = execution.id === activeId
      const streamed =
        isActive && liveText ? liveText : String(execution.output_data?.value ?? '')
      return {
        id: execution.id,
        execution,
        status: execution.status,
        input: String(execution.input_data?.value ?? ''),
        output: streamed,
        error: execution.error,
        isActive,
      }
    })
}

export function ChatPanel({
  workflowName,
  hasWorkflow,
  activeWorkflowId,
  executions,
  liveTokens,
  lastExecution,
  runEnabled,
  runDisabledReason,
  loading,
  cancelling,
  nodeMetaByNodeId,
  onRun,
  onCancel,
}: ChatPanelProps) {
  const [draft, setDraft] = useState('')
  const [versionNumbers, setVersionNumbers] = useState<Record<number, number>>({})
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const activeExecutionId = useMemo(
    () =>
      lastExecution && ACTIVE_STATUSES.includes(lastExecution.status)
        ? lastExecution.id
        : null,
    [lastExecution],
  )
  const isRunning = activeExecutionId !== null
  const outputNodeId = useMemo(
    () => findOutputNodeId(nodeMetaByNodeId),
    [nodeMetaByNodeId],
  )
  const liveText = liveOutputText(liveTokens, outputNodeId)

  const turns = useMemo(
    () => buildTurns(executions, activeExecutionId, liveText),
    [executions, activeExecutionId, liveText],
  )

  useEffect(() => {
    if (activeWorkflowId === null) {
      return
    }
    let cancelled = false
    getWorkflowVersions(activeWorkflowId)
      .then((versions) => {
        if (cancelled) {
          return
        }
        const map: Record<number, number> = {}
        for (const version of versions) {
          map[version.id] = version.version
        }
        setVersionNumbers(map)
      })
      .catch(() => {
        // version labels are best-effort; ignore fetch failures
      })
    return () => {
      cancelled = true
    }
  }, [activeWorkflowId])

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) {
      return
    }
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight
    if (distanceFromBottom <= NEAR_BOTTOM_THRESHOLD_PX) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [turns])

  const canSend = runEnabled && !isRunning && !loading && draft.trim().length > 0

  function handleSend(): void {
    if (!canSend) {
      return
    }
    onRun({ value: draft.trim() })
    setDraft('')
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  const placeholder = !hasWorkflow
    ? 'Select a workflow in Build mode first.'
    : runDisabledReason ?? 'Type a message to run the flow...'

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-xs text-[var(--muted)]">{workflowName}</div>
        {isRunning ? (
          <div className="flex items-center gap-2">
            <span className="live-dot" />
            <span className="text-xs text-[var(--muted)]">running…</span>
            <button
              type="button"
              className="pixel-button ghost small"
              disabled={cancelling}
              onClick={onCancel}
            >
              {cancelling ? 'Cancelling…' : 'Cancel run'}
            </button>
          </div>
        ) : null}
      </div>

      <div ref={scrollContainerRef} className="pixel-scroll flex-1 overflow-y-auto pr-1">
        {turns.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--muted)]">
            {hasWorkflow
              ? 'No test runs yet. Send a message to try this flow before it goes live.'
              : 'Select a workflow in Build mode to start testing.'}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {turns.map((turn) => (
              <ChatTurnView
                key={turn.id}
                turn={turn}
                versionNumber={
                  turn.execution.version_id !== null
                    ? versionNumbers[turn.execution.version_id]
                    : undefined
                }
                nodeMetaByNodeId={nodeMetaByNodeId}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="mt-3 border-t border-white/10 pt-3">
        <div className="flex items-end gap-2">
          <textarea
            className="pixel-textarea min-h-[56px] flex-1"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={!hasWorkflow || !runEnabled || isRunning || loading}
            placeholder={placeholder}
          />
          <button
            type="button"
            className="pixel-button small"
            disabled={!canSend}
            onClick={handleSend}
          >
            {isRunning ? 'Running…' : 'Send'}
          </button>
        </div>
        {hasWorkflow && runDisabledReason ? (
          <div className="mt-2 text-xs text-[var(--danger)]">{runDisabledReason}</div>
        ) : null}
      </div>
    </div>
  )
}

function ChatTurnView({
  turn,
  versionNumber,
  nodeMetaByNodeId,
}: {
  turn: ChatTurn
  versionNumber: number | undefined
  nodeMetaByNodeId: Map<number, NodeMeta>
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-end">
        <div className="pixel-panel max-w-[80%] whitespace-pre-wrap px-3 py-2 text-sm">
          {turn.input || <span className="text-[var(--muted)]">(empty input)</span>}
        </div>
      </div>
      <div className="flex justify-start">
        <ChatTurnResponse turn={turn} />
      </div>
      <div className="flex items-center gap-2 pl-1 text-[10px] uppercase tracking-wide text-[var(--muted)]">
        <span className={STATUS_COLORS[turn.status]}>{turn.status}</span>
        {versionNumber !== undefined ? (
          <span className="pixel-pill text-[10px]">v{versionNumber}</span>
        ) : null}
        <span>{formatTime(turn.execution.started_at)}</span>
        {turn.execution.finished_at ? (
          <span>→ {formatTime(turn.execution.finished_at)}</span>
        ) : null}
        <ExecutionDetails executionId={turn.id} nodeMetaByNodeId={nodeMetaByNodeId} />
      </div>
    </div>
  )
}

function ChatTurnResponse({ turn }: { turn: ChatTurn }) {
  if (turn.status === 'cancelled') {
    return (
      <div className="pixel-panel max-w-[80%] px-3 py-2 text-sm text-[var(--muted)]">
        Execution cancelled.
      </div>
    )
  }

  if (turn.status === 'failed') {
    return (
      <div className="pixel-error max-w-[80%] whitespace-pre-wrap text-sm">
        {turn.error ?? 'Execution failed.'}
      </div>
    )
  }

  if (turn.status === 'success' || turn.output) {
    return (
      <div className="pixel-panel max-w-[80%] whitespace-pre-wrap border-[rgba(53,255,188,0.4)] px-3 py-2 text-sm">
        {turn.output}
        {turn.isActive ? <span className="live-dot ml-2 inline-block align-middle" /> : null}
      </div>
    )
  }

  return (
    <div className="pixel-panel flex max-w-[80%] items-center gap-2 px-3 py-2 text-sm text-[var(--muted)]">
      <span className="live-dot" />
      thinking…
    </div>
  )
}
