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
  const inputPorts = data.graph.inputs ?? []
  const outputPorts = data.graph.outputs ?? []
  const inputPortKey = inputPorts.map((port) => port.name).join(':')
  const outputPortKey = outputPorts.map((port) => port.name).join(':')
  const updateNodeInternals = useUpdateNodeInternals()

  // reactflow caches each handle's DOM position for edge routing and only
  // remeasures on an explicit nudge — without this, edges keep anchoring to
  // stale coordinates whenever a node's handle count/layout changes.
  useEffect(() => {
    updateNodeInternals(id)
  }, [id, inputPortKey, outputHandles, outputPortKey, updateNodeInternals])

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
      {inputPorts.length > 0 ? (
        <>
          <div className="flex justify-around border-b border-white/10 pb-1 text-[10px] leading-none text-[var(--muted)]">
            {inputPorts.map((port) => (
              <span key={port.name}>
                ↑ {port.label}: {resolvePortType(port, { ...data })}
              </span>
            ))}
          </div>
          {inputPorts.map((port, index) => (
            <Handle
              key={port.name}
              type="target"
              id={index === 0 ? undefined : port.name}
              position={Position.Top}
              style={{ left: handleLeft(index, inputPorts.length) }}
            />
          ))}
        </>
      ) : null}
      <div className="flex items-center gap-2">
        <NodeIcon iconKey={data.iconKey} />
        {data.label}
      </div>
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
      {outputHandles && outputHandles.length > 0 ? (
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
      ) : outputPorts.length > 0 ? (
        <>
          <div className="flex justify-around border-t border-white/10 pt-1 text-[10px] leading-none text-[var(--muted)]">
            {outputPorts.map((port) => (
              <span key={port.name}>
                ↓ {port.label}: {resolvePortType(port, { ...data })}
              </span>
            ))}
          </div>
          {outputPorts.map((port, index) => (
            <Handle
              key={port.name}
              type="source"
              id={index === 0 ? undefined : port.name}
              position={Position.Bottom}
              style={{ left: handleLeft(index, outputPorts.length) }}
            />
          ))}
        </>
      ) : null}
    </div>
  )
}
