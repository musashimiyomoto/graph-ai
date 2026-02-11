import type { NodeProps } from 'reactflow'
import { Handle, Position } from 'reactflow'

import { NodeIcon } from './NodeIcons'

interface NodeData {
  label: string
  iconKey: string
  graph: {
    has_input: boolean
    has_output: boolean
  }
}

export function GenericNode({ data }: NodeProps<NodeData>) {
  return (
    <div className="pixel-node flex items-center gap-2">
      {data.graph.has_input ? <Handle type="target" position={Position.Top} /> : null}
      <NodeIcon iconKey={data.iconKey} />
      {data.label}
      {data.graph.has_output ? <Handle type="source" position={Position.Bottom} /> : null}
    </div>
  )
}
