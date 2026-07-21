import { useState } from 'react'

import { getExecutionNodeResults } from '../lib/api'
import { formatDuration, STATUS_COLORS } from '../lib/executionFormat'
import type { NodeExecutionResult, NodeMeta } from '../lib/types'
import { OutputRenderer } from './OutputRenderer'

interface ExecutionDetailsProps {
  executionId: number
  nodeMetaByNodeId: Map<number, NodeMeta>
}

interface IterationGroup {
  parentNodeId: number
  iteration: number
  results: NodeExecutionResult[]
}

type DisplayEntry =
  | { kind: 'flat'; result: NodeExecutionResult }
  | { kind: 'iteration'; group: IterationGroup }

// Groups consecutive rows sharing the same (Loop node, iteration) into one
// entry per iteration; everything else (including the Loop node's own row)
// stays flat, in its original order. Consecutive-only grouping is enough
// because the backend always finishes recording one Loop's iterations
// before its own row, and before the next Loop starts (see
// `ExecutionUsecase._run_loop_list`/`_run_loop_condition`).
function groupByIteration(
  nodeResults: NodeExecutionResult[],
  nodeMetaByNodeId: Map<number, NodeMeta>,
): DisplayEntry[] {
  const entries: DisplayEntry[] = []
  let currentGroup: IterationGroup | null = null

  for (const result of nodeResults) {
    const parentNodeId =
      result.iteration !== null
        ? (nodeMetaByNodeId.get(result.node_id)?.parentNodeId ?? null)
        : null

    if (result.iteration === null || parentNodeId === null) {
      currentGroup = null
      entries.push({ kind: 'flat', result })
      continue
    }

    if (
      currentGroup &&
      currentGroup.parentNodeId === parentNodeId &&
      currentGroup.iteration === result.iteration
    ) {
      currentGroup.results.push(result)
      continue
    }

    currentGroup = { parentNodeId, iteration: result.iteration, results: [result] }
    entries.push({ kind: 'iteration', group: currentGroup })
  }

  return entries
}

function NodeResultRow({
  nodeResult,
  nodeMetaByNodeId,
}: {
  nodeResult: NodeExecutionResult
  nodeMetaByNodeId: Map<number, NodeMeta>
}) {
  const meta = nodeMetaByNodeId.get(nodeResult.node_id)
  const duration = formatDuration(nodeResult.started_at, nodeResult.finished_at)
  const outputEntries = Object.entries(nodeResult.output_values ?? {})

  return (
    <div className="border-b border-white/10 pb-2 last:border-0 last:pb-0">
      <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
        <span className="pixel-pill text-[10px] normal-case">
          {meta?.label ?? nodeResult.node_label ?? `Node #${nodeResult.node_id}`}
        </span>
        <span className={STATUS_COLORS[nodeResult.status]}>{nodeResult.status}</span>
        {duration ? <span>{duration}</span> : null}
      </div>
      {outputEntries.length > 0 ? (
        <div className="space-y-2">
          {outputEntries.map(([handle, typedValue]) => (
            <div key={handle}>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-[var(--muted)]">
                {handle}
              </div>
              <OutputRenderer value={null} typedValue={typedValue} />
            </div>
          ))}
        </div>
      ) : nodeResult.output !== null || nodeResult.output_value !== null ? (
        <OutputRenderer
          value={nodeResult.output}
          typedValue={nodeResult.output_value}
          portType={meta?.portType ?? null}
        />
      ) : null}
      {nodeResult.status === 'waiting_delay' && nodeResult.wait_until ? (
        <div className="text-[var(--muted)]">
          Waiting until {new Date(nodeResult.wait_until).toLocaleString()}
        </div>
      ) : null}
      {nodeResult.error ? <div className="text-[var(--danger)]">{nodeResult.error}</div> : null}
    </div>
  )
}

function IterationAccordion({
  group,
  nodeMetaByNodeId,
}: {
  group: IterationGroup
  nodeMetaByNodeId: Map<number, NodeMeta>
}) {
  const [expanded, setExpanded] = useState(false)
  const loopLabel = nodeMetaByNodeId.get(group.parentNodeId)?.label ?? 'Loop'
  const hasFailure = group.results.some((result) => result.status === 'failed')

  return (
    <div className="border-b border-white/10 pb-2 last:border-0 last:pb-0">
      <button
        type="button"
        className="pixel-link flex w-full items-center gap-2 text-left underline"
        onClick={() => setExpanded((previous) => !previous)}
      >
        <span>{expanded ? '▾' : '▸'}</span>
        <span>
          {loopLabel} — Iteration {group.iteration}
        </span>
        <span className="text-[var(--muted)]">({group.results.length} node(s))</span>
        {hasFailure ? <span className={STATUS_COLORS.failed}>failed</span> : null}
      </button>
      {expanded ? (
        <div className="mt-2 flex flex-col gap-2 pl-4">
          {group.results.map((result) => (
            <NodeResultRow key={result.id} nodeResult={result} nodeMetaByNodeId={nodeMetaByNodeId} />
          ))}
        </div>
      ) : null}
    </div>
  )
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
            groupByIteration(nodeResults, nodeMetaByNodeId).map((entry) =>
              entry.kind === 'flat' ? (
                <NodeResultRow
                  key={entry.result.id}
                  nodeResult={entry.result}
                  nodeMetaByNodeId={nodeMetaByNodeId}
                />
              ) : (
                <IterationAccordion
                  key={`${entry.group.parentNodeId}:${entry.group.iteration}:${entry.group.results[0].id}`}
                  group={entry.group}
                  nodeMetaByNodeId={nodeMetaByNodeId}
                />
              ),
            )
          )}
        </div>
      ) : null}
    </>
  )
}
