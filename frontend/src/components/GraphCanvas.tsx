import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  DefaultEdgeOptions,
  Connection,
  Edge,
  EdgeMouseHandler,
  Node as FlowNode,
  NodeChange,
  NodeMouseHandler,
  NodeTypes,
  OnSelectionChangeFunc,
} from 'reactflow'
import ReactFlow, {
  Background,
  ConnectionLineType,
  Controls,
  MarkerType,
  ReactFlowProvider,
  SelectionMode,
  useReactFlow,
} from 'reactflow'

import type { NodeCatalogItem } from '../lib/types'
import { GenericNode } from './CustomNodes'
import { ContextMenu } from './NodeContextMenu'

interface GraphCanvasProps {
  // Included only to trigger the fitView-on-workflow-switch effect below —
  // GraphCanvas never unmounts between workflows (only its nodes/edges
  // props change), so React Flow's own `fitView` prop (mount-only) never
  // re-centers on switch; watching this id is the trigger that does.
  activeWorkflowId: number | null
  nodes: FlowNode[]
  edges: Edge[]
  nodeCatalog: NodeCatalogItem[]
  runDisabledReason: string | null
  selectedCount: number
  onSelectionChange: (nodeIds: string[], edgeIds: string[]) => void
  onNodesChange: (changes: NodeChange[]) => void
  onMoveNode: (id: string, x: number, y: number) => void
  onConnect: (sourceId: string, targetId: string, sourceHandle: string | null) => void
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
  activeWorkflowId,
  nodes,
  edges,
  nodeCatalog,
  runDisabledReason,
  selectedCount,
  onSelectionChange,
  onNodesChange,
  onMoveNode,
  onConnect,
  onDeleteEdge,
  onDropNode,
  onDeleteNode,
}: GraphCanvasProps) {
  const { screenToFlowPosition, fitView } = useReactFlow()
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)

  // React Flow's own `fitView` prop only centers on mount; GraphCanvas stays
  // mounted across workflow switches (only nodes/edges change), so without
  // this the camera stays wherever it was left on the previous workflow —
  // including right after creating one from a template, where it visibly
  // doesn't center on the new graph at all. `activeWorkflowId` flips before
  // its nodes have finished loading (the fetch in useGraphState is async),
  // so we arm on the id change but wait for that workflow's first non-empty
  // `nodes` update before actually re-centering — fitting an empty/stale
  // graph would just leave the camera wherever it already was.
  const pendingFitWorkflowId = useRef<number | null>(null)
  useEffect(() => {
    pendingFitWorkflowId.current = activeWorkflowId
  }, [activeWorkflowId])
  useEffect(() => {
    if (pendingFitWorkflowId.current === null || nodes.length === 0) {
      return
    }
    pendingFitWorkflowId.current = null
    const raf = requestAnimationFrame(() => fitView({ duration: 200 }))
    return () => cancelAnimationFrame(raf)
  }, [nodes, fitView])

  const catalogByType = useMemo(
    () => Object.fromEntries(nodeCatalog.map((item) => [item.type, item])),
    [nodeCatalog],
  )
  const nodeTypeById = useMemo(
    () =>
      Object.fromEntries(
        nodes.map((node) => [node.id, String(node.data?.nodeType ?? node.type)]),
      ),
    [nodes],
  )

  const isValidConnection = useCallback(
    (connection: Connection): boolean => {
      if (!connection.source || !connection.target) {
        return false
      }
      if (connection.source === connection.target) {
        return false
      }
      const sourceGraph = catalogByType[nodeTypeById[connection.source]]?.graph
      const targetGraph = catalogByType[nodeTypeById[connection.target]]?.graph
      if (!sourceGraph || !targetGraph) {
        return true
      }
      const output = sourceGraph.output_port
      const input = targetGraph.input_port
      if (!output || !input) {
        return false
      }
      return output === input
    },
    [catalogByType, nodeTypeById],
  )

  const defaultEdgeOptions = useMemo<DefaultEdgeOptions>(
    () => ({
      type: 'step',
      className: 'pixel-edge',
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 12,
        height: 12,
        color: '#35ffbc',
      },
      style: {
        strokeWidth: 2.5,
        stroke: '#35ffbc',
      },
    }),
    [],
  )

  const nodeTypes = useMemo<NodeTypes>(() => {
    const entries: Array<[string, NodeTypes[string]]> = nodeCatalog.map((item) => [
      item.type,
      GenericNode,
    ])
    return Object.fromEntries(entries)
  }, [nodeCatalog])

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

  const handleSelectionChange = useCallback<OnSelectionChangeFunc>(
    ({ nodes: selectedNodes, edges: selectedEdges }) => {
      onSelectionChange(
        selectedNodes.map((node) => node.id),
        selectedEdges.map((edge) => edge.id),
      )
    },
    [onSelectionChange],
  )

  return (
    <section className="pixel-canvas relative h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onSelectionChange={handleSelectionChange}
        // Left-drag box-selects (rather than panning) once multi-select
        // exists; pan moves to middle/right-mouse-drag instead. Delete/
        // Backspace is handled by our own app-level shortcut (which calls
        // the delete API + records an undo command) instead of React
        // Flow's built-in `deleteKeyCode`, which would otherwise silently
        // drop selected nodes from local state without deleting them
        // server-side.
        selectionMode={SelectionMode.Partial}
        selectionOnDrag
        panOnDrag={[1, 2]}
        multiSelectionKeyCode="Shift"
        deleteKeyCode={null}
        onNodeClick={() => setContextMenu(null)}
        onPaneClick={() => setContextMenu(null)}
        onNodeContextMenu={handleNodeContextMenu}
        onEdgeContextMenu={handleEdgeContextMenu}
        onNodeDragStop={(_, node) =>
          onMoveNode(node.id, node.position.x, node.position.y)
        }
        onConnect={(params: Connection) => {
          if (params.source && params.target) {
            onConnect(params.source, params.target, params.sourceHandle)
          }
        }}
        isValidConnection={isValidConnection}
        defaultEdgeOptions={defaultEdgeOptions}
        connectionLineType={ConnectionLineType.Step}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        proOptions={{ hideAttribution: true }}
        fitView
      >
        <Background gap={24} color="rgba(255,255,255,0.08)" />
        <Controls />
      </ReactFlow>
      {runDisabledReason ? (
        <div className="pixel-pill absolute left-3 top-3 z-10 max-w-[70%] text-[var(--muted)]">
          Can't run: {runDisabledReason}
        </div>
      ) : null}
      {selectedCount > 1 ? (
        <div className="pixel-pill absolute right-3 top-3 z-10 text-[var(--muted)]">
          {selectedCount} selected
        </div>
      ) : null}
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
