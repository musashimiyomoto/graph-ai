import { useState } from 'react'

import { getExecutionNodeResults } from '../lib/api'
import { formatDuration, STATUS_COLORS } from '../lib/executionFormat'
import type { NodeExecutionResult, NodeMeta } from '../lib/types'
import { OutputRenderer } from './OutputRenderer'

interface ExecutionDetailsProps {
  executionId: number
  nodeMetaByNodeId: Map<number, NodeMeta>
}

// Expandable per-node breakdown for one execution, shared by Test Runs and
// the Activity Log so debugging a run looks the same regardless of who
// triggered it.
export function ExecutionDetails({
  executionId,
  nodeMetaByNodeId,
}: ExecutionDetailsProps) {
  const [open, setOpen] = useState(false)
  const [nodeResults, setNodeResults] = useState<NodeExecutionResult[] | null>(null)
  const [loading, setLoading] = useState(false)

  function toggle(): void {
    const opening = !open
    setOpen(opening)
    if (opening && nodeResults === null) {
      setLoading(true)
      getExecutionNodeResults(executionId)
        .then((results) => setNodeResults(results))
        .catch(() => setNodeResults([]))
        .finally(() => setLoading(false))
    }
  }

  return (
    <>
      <button type="button" className="pixel-link underline" onClick={toggle}>
        {open ? 'Hide details' : 'Details'}
      </button>
      {open ? (
        <div className="pixel-panel ml-1 flex flex-col gap-2 px-3 py-2 text-xs">
          {loading ? (
            <div className="text-[var(--muted)]">Loading node results…</div>
          ) : !nodeResults || nodeResults.length === 0 ? (
            <div className="text-[var(--muted)]">No node results recorded.</div>
          ) : (
            nodeResults.map((nodeResult) => {
              const meta = nodeMetaByNodeId.get(nodeResult.node_id)
              const duration = formatDuration(
                nodeResult.started_at,
                nodeResult.finished_at,
              )
              return (
                <div
                  key={nodeResult.id}
                  className="border-b border-white/10 pb-2 last:border-0 last:pb-0"
                >
                  <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
                    <span className="pixel-pill text-[10px] normal-case">
                      {meta?.label ??
                        nodeResult.node_label ??
                        `Node #${nodeResult.node_id}`}
                    </span>
                    <span className={STATUS_COLORS[nodeResult.status]}>
                      {nodeResult.status}
                    </span>
                    {duration ? <span>{duration}</span> : null}
                  </div>
                  {nodeResult.output !== null ? (
                    <OutputRenderer
                      value={nodeResult.output}
                      portType={meta?.portType ?? null}
                    />
                  ) : null}
                  {nodeResult.error ? (
                    <div className="text-[var(--danger)]">{nodeResult.error}</div>
                  ) : null}
                </div>
              )
            })
          )}
        </div>
      ) : null}
    </>
  )
}
