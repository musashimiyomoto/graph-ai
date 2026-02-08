import { useCallback, useState } from 'react'
import type { Connection, Edge, EdgeMouseHandler, Node as FlowNode, NodeChange, NodeMouseHandler } from 'reactflow'
import ReactFlow, { Background, Controls, ReactFlowProvider, useReactFlow } from 'reactflow'

import { InputNode, LlmNode, OutputNode } from './CustomNodes'
import { ContextMenu } from './NodeContextMenu'

const nodeTypes = { input: InputNode, llm: LlmNode, output: OutputNode }

interface GraphCanvasProps {
  nodes: FlowNode[]
  edges: Edge[]
  onSelectNode: (id: string | null) => void
  onNodesChange: (changes: NodeChange[]) => void
  onMoveNode: (id: string, x: number, y: number) => void
  onConnect: (sourceId: string, targetId: string) => void
  onDeleteEdge: (edgeId: string) => void
  onDropNode: (type: string, position: { x: number; y: number }) => void
  onDeleteNode: (id: string) => void
}

interface ContextMenuState {
  id: string
  label: string
  type: 'node' | 'edge'
  x: number
  y: number
}

function GraphCanvasInner({
  nodes,
  edges,
  onSelectNode,
  onNodesChange,
  onMoveNode,
  onConnect,
  onDeleteEdge,
  onDropNode,
  onDeleteNode,
}: GraphCanvasProps) {
  const { screenToFlowPosition } = useReactFlow()
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const type = event.dataTransfer.getData('application/graphai-node-type')
      if (!type) {
        return
      }
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })
      onDropNode(type, position)
    },
    [screenToFlowPosition, onDropNode],
  )

  const handleNodeContextMenu: NodeMouseHandler = useCallback(
    (event, node) => {
      event.preventDefault()
      setContextMenu({
        id: node.id,
        label: (node.data as { label?: string }).label ?? node.id,
        type: 'node',
        x: event.clientX,
        y: event.clientY,
      })
    },
    [],
  )

  const handleEdgeContextMenu: EdgeMouseHandler = useCallback(
    (event, edge) => {
      event.preventDefault()
      const sourceName = (nodes.find((n) => n.id === edge.source)?.data?.label as string) ?? edge.source
      const targetName = (nodes.find((n) => n.id === edge.target)?.data?.label as string) ?? edge.target
      setContextMenu({
        id: edge.id,
        label: `${sourceName} → ${targetName}`,
        type: 'edge',
        x: event.clientX,
        y: event.clientY,
      })
    },
    [nodes],
  )

  const handleDeleteFromMenu = useCallback(() => {
    if (!contextMenu) {
      return
    }
    if (contextMenu.type === 'node') {
      onDeleteNode(contextMenu.id)
    } else {
      onDeleteEdge(contextMenu.id)
    }
    setContextMenu(null)
  }, [contextMenu, onDeleteNode, onDeleteEdge])

  const closeContextMenu = useCallback(() => {
    setContextMenu(null)
  }, [])

  return (
    <section className="pixel-canvas relative h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={(_, node) => {
          onSelectNode(node.id)
          setContextMenu(null)
        }}
        onPaneClick={() => {
          onSelectNode(null)
          setContextMenu(null)
        }}
        onNodeContextMenu={handleNodeContextMenu}
        onEdgeContextMenu={handleEdgeContextMenu}
        onNodeDragStop={(_, node) =>
          onMoveNode(node.id, node.position.x, node.position.y)
        }
        onConnect={(params: Connection) => {
          if (params.source && params.target) {
            onConnect(params.source, params.target)
          }
        }}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        proOptions={{ hideAttribution: true }}
        fitView
      >
        <Background gap={24} color="rgba(255,255,255,0.08)" />
        <Controls />
      </ReactFlow>
      {contextMenu ? (
        <ContextMenu
          label={contextMenu.label}
          x={contextMenu.x}
          y={contextMenu.y}
          onDelete={handleDeleteFromMenu}
          onClose={closeContextMenu}
        />
      ) : null}
    </section>
  )
}

export function GraphCanvas(props: GraphCanvasProps) {
  return (
    <ReactFlowProvider>
      <GraphCanvasInner {...props} />
    </ReactFlowProvider>
  )
}
