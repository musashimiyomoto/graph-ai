import type { Connection, Edge, Node as FlowNode } from 'reactflow'
import ReactFlow, { Background, Controls } from 'reactflow'

interface GraphCanvasProps {
  nodes: FlowNode[]
  edges: Edge[]
  selectedNodeId: string | null
  onSelectNode: (id: string | null) => void
  onMoveNode: (id: string, x: number, y: number) => void
  onConnect: (sourceId: string, targetId: string) => void
  onDeleteEdge: (edgeId: string) => void
}

export function GraphCanvas({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  onMoveNode,
  onConnect,
  onDeleteEdge,
}: GraphCanvasProps) {
  return (
    <section className="pixel-canvas h-full">
      <ReactFlow
        nodes={nodes.map((node) => ({
          ...node,
          selected: node.id === selectedNodeId,
          className: 'pixel-node',
        }))}
        edges={edges}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onPaneClick={() => onSelectNode(null)}
        onNodeDragStop={(_, node) =>
          onMoveNode(node.id, node.position.x, node.position.y)
        }
        onConnect={(params: Connection) => {
          if (params.source && params.target) {
            onConnect(params.source, params.target)
          }
        }}
        onEdgesChange={(changes) => {
          changes.forEach((change) => {
            if (change.type === 'remove') {
              onDeleteEdge(String(change.id))
            }
          })
        }}
        fitView
      >
        <Background gap={24} color="rgba(255,255,255,0.08)" />
        <Controls />
      </ReactFlow>
    </section>
  )
}
