import { formatTime, STATUS_COLORS } from '../lib/executionFormat'
import type { Execution, NodeMeta } from '../lib/types'
import { ApprovalActions } from './ApprovalActions'
import { ExecutionDetails } from './ExecutionDetails'

interface ActivityLogProps {
  workflowName: string
  hasWorkflow: boolean
  executions: Execution[]
  loading: boolean
  decidingExecutionId: number | null
  nodeMetaByNodeId: Map<number, NodeMeta>
  onApprove: (executionId: number) => void
  onReject: (executionId: number) => void
}

// Log of real inbound traffic from connected channels, separate from Test Runs
// so actual usage is never confused with the owner's trial-and-error. Pending
// Approval nodes remain actionable from this operational view.
export function ActivityLog({
  workflowName,
  hasWorkflow,
  executions,
  loading,
  decidingExecutionId,
  nodeMetaByNodeId,
  onApprove,
  onReject,
}: ActivityLogProps) {
  const sorted = [...executions].sort((first, second) => second.id - first.id)

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="mb-3 text-xs text-[var(--muted)]">{workflowName}</div>

      <div className="pixel-scroll flex-1 overflow-y-auto pr-1">
        {!hasWorkflow ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--muted)]">
            Select a workflow in Build mode to see its activity.
          </div>
        ) : loading && sorted.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--muted)]">
            Loading…
          </div>
        ) : sorted.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--muted)]">
            No real traffic yet. Runs from a connected channel or webhook will
            show up here.
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {sorted.map((execution) => (
              <div key={execution.id} className="pixel-panel flex flex-col gap-2 px-3 py-2 text-sm">
                <div className="whitespace-pre-wrap">
                  {String(execution.input_data?.value ?? '') || (
                    <span className="text-[var(--muted)]">(empty input)</span>
                  )}
                </div>
                {execution.status === 'waiting_approval' ? (
                  <ApprovalActions
                    execution={execution}
                    deciding={decidingExecutionId === execution.id}
                    onApprove={onApprove}
                    onReject={onReject}
                  />
                ) : execution.status === 'waiting_delay' ? (
                  <div className="text-[var(--muted)]">
                    Waiting until{' '}
                    {execution.wait_until
                      ? formatTime(execution.wait_until)
                      : 'the configured time'}
                    .
                  </div>
                ) : execution.status === 'failed' ? (
                  <div className="pixel-error whitespace-pre-wrap text-sm">
                    {execution.error ?? 'Execution failed.'}
                  </div>
                ) : execution.status === 'rejected' ? (
                  <div className="text-[var(--muted)]">Execution rejected.</div>
                ) : execution.status === 'cancelled' ? (
                  <div className="text-[var(--muted)]">Execution cancelled.</div>
                ) : (
                  <div className="whitespace-pre-wrap text-[var(--muted)]">
                    {String(execution.output_data?.value ?? '')}
                  </div>
                )}
                <div className="flex items-center gap-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
                  <span className={STATUS_COLORS[execution.status]}>
                    {execution.status}
                  </span>
                  <span className="pixel-pill text-[10px] normal-case">
                    {execution.source}
                  </span>
                  <span>{formatTime(execution.started_at)}</span>
                  {execution.finished_at ? (
                    <span>→ {formatTime(execution.finished_at)}</span>
                  ) : null}
                  <ExecutionDetails
                    executionId={execution.id}
                    nodeMetaByNodeId={nodeMetaByNodeId}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
