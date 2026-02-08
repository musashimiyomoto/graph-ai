import type { NodeProps } from 'reactflow'
import { Handle, Position } from 'reactflow'

import { InputIcon, LlmIcon, OutputIcon } from './NodeIcons'

interface NodeData {
  label: string
}

export function InputNode({ data }: NodeProps<NodeData>) {
  return (
    <div className="pixel-node flex items-center gap-2">
      <InputIcon />
      {data.label}
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

export function LlmNode({ data }: NodeProps<NodeData>) {
  return (
    <div className="pixel-node flex items-center gap-2">
      <Handle type="target" position={Position.Top} />
      <LlmIcon />
      {data.label}
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

export function OutputNode({ data }: NodeProps<NodeData>) {
  return (
    <div className="pixel-node flex items-center gap-2">
      <Handle type="target" position={Position.Top} />
      <OutputIcon />
      {data.label}
    </div>
  )
}
