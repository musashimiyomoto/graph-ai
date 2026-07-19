import type { Execution } from '../lib/types'

interface ApprovalActionsProps {
  execution: Execution
  deciding: boolean
  onApprove: (executionId: number) => void
  onReject: (executionId: number) => void
}

export function ApprovalActions({
  execution,
  deciding,
  onApprove,
  onReject,
}: ApprovalActionsProps) {
  return (
    <div className="flex max-w-[640px] flex-col gap-2 border-l-2 border-[var(--accent-2)] pl-3">
      <div className="text-sm text-[var(--text)]">
        {execution.approval_prompt ?? 'Approval required.'}
      </div>
      {execution.approval_input ? (
        <pre className="pixel-scroll max-h-40 overflow-auto whitespace-pre-wrap text-xs text-[var(--muted)]">
          {execution.approval_input}
        </pre>
      ) : null}
      <div className="flex gap-2">
        <button
          type="button"
          className="pixel-button small"
          disabled={deciding}
          onClick={() => onApprove(execution.id)}
        >
          {deciding ? 'Saving…' : 'Approve'}
        </button>
        <button
          type="button"
          className="pixel-button ghost small"
          disabled={deciding}
          onClick={() => onReject(execution.id)}
        >
          Reject
        </button>
      </div>
    </div>
  )
}
