import { useEffect } from 'react'
import type { NodeProps } from 'reactflow'
import { Handle, Position, useUpdateNodeInternals } from 'reactflow'

import { resolvePortType } from '../lib/ports'
import type { NodePortSpec } from '../lib/types'
import { NodeIcon } from './NodeIcons'

interface NodeData {
  label: string
  iconKey: string
  nodeType?: string
  // Only set on Loop nodes (see App.tsx) — how many nodes live in its body,
  // shown alongside the "double-click to open" hint below.
  childCount?: number
  graph: {
    has_input: boolean
    has_output: boolean
    output_handles?: string[] | null
    inputs?: NodePortSpec[]
    outputs?: NodePortSpec[]
  }
}

// Evenly space N named handles along the bottom edge (matches the 50%
// center a single default handle gets).
function handleLeft(index: number, count: number): string {
  return `${((index + 1) / (count + 1)) * 100}%`
}

export function GenericNode({ id, data }: NodeProps<NodeData>) {
  const outputHandles = data.graph.output_handles
  const inputPort = data.graph.inputs?.[0]
  const outputPort = data.graph.outputs?.[0]
  const inputType = resolvePortType(inputPort, { ...data })
  const outputType = resolvePortType(outputPort, { ...data })
  const updateNodeInternals = useUpdateNodeInternals()

  // reactflow caches each handle's DOM position for edge routing and only
  // remeasures on an explicit nudge — without this, edges keep anchoring to
  // stale coordinates whenever a node's handle count/layout changes.
  useEffect(() => {
    updateNodeInternals(id)
  }, [id, outputHandles, updateNodeInternals])

  const isLoop = data.nodeType === 'loop'
  const isCallWorkflow = data.nodeType === 'call_workflow'
  const drilldownTitle = isLoop
    ? 'Double-click to open this loop’s body'
    : isCallWorkflow
      ? 'Double-click to open the called workflow'
      : undefined

  return (
    <div
      className={`pixel-node flex flex-col gap-1 ${isLoop ? 'border-dashed' : ''}`}
      title={drilldownTitle}
    >
      <div className="flex items-center gap-2">
        {data.graph.has_input ? <Handle type="target" position={Position.Top} /> : null}
        <NodeIcon iconKey={data.iconKey} />
        {data.label}
      </div>
      {inputPort && inputType ? (
        <div className="text-[10px] leading-none text-[var(--muted)]">
          ↑ {inputPort.label}: {inputType}
        </div>
      ) : null}
      {isLoop ? (
        <div className="flex items-center gap-1 border-t border-white/10 pt-1 text-[10px] leading-none text-[var(--muted)]">
          <span>⤢ Double-click to open</span>
          {data.childCount !== undefined ? (
            <span>
              ({data.childCount} node{data.childCount === 1 ? '' : 's'})
            </span>
          ) : null}
        </div>
      ) : null}
      {data.graph.has_output && outputHandles && outputHandles.length > 0 ? (
        <>
          <div className="flex justify-around border-t border-white/10 pt-1 text-[10px] leading-none text-[var(--muted)]">
            {outputHandles.map((handle) => (
              <span key={handle}>{handle}</span>
            ))}
          </div>
          {outputHandles.map((handle, index) => (
            <Handle
              key={handle}
              type="source"
              id={handle}
              position={Position.Bottom}
              style={{ left: handleLeft(index, outputHandles.length) }}
            />
          ))}
        </>
      ) : data.graph.has_output ? (
        <>
          {outputPort && outputType ? (
            <div className="border-t border-white/10 pt-1 text-[10px] leading-none text-[var(--muted)]">
              ↓ {outputPort.label}: {outputType}
            </div>
          ) : null}
          <Handle type="source" position={Position.Bottom} />
        </>
      ) : null}
    </div>
  )
}
