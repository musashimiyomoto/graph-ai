import { useEffect, useRef } from 'react'
import type { Edge, Node as FlowNode, NodeChange } from 'reactflow'

import type { NodeCatalogItem, NodeType } from '../lib/types'
import { GraphCanvas } from './GraphCanvas'
import { InspectorPanel } from './InspectorPanel'
import { NodePalette } from './NodePalette'

interface LoopBodyModalProps {
  loopNodeId: number
  loopLabel: string
  activeWorkflowId: number | null
  nodes: FlowNode[]
  edges: Edge[]
  nodeCatalog: NodeCatalogItem[]
  creatableNodeCatalog: NodeCatalogItem[]
  selectedNode: FlowNode | null
  selectedCount: number
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onAutoLayout: () => void
  onSelectionChange: (nodeIds: string[], edgeIds: string[]) => void
  onNodesChange: (changes: NodeChange[]) => void
  onMoveNode: (id: string, x: number, y: number) => void
  onConnect: (sourceId: string, targetId: string, sourceHandle: string | null) => void
  onDeleteEdge: (edgeId: string) => void
  onDropNode: (type: string, position: { x: number; y: number }) => void
  onDeleteNode: (id: string) => void
  onAddNode: (type: NodeType) => void
  onSaveNode: (id: string, data: Record<string, unknown>) => Promise<boolean>
  onOpenCalledWorkflow: (workflowId: number) => void
  onClose: () => void
}

// Full-screen overlay for editing a Loop node's body — rather than swapping
// out the main canvas (which made it easy to forget you'd navigated away
// from the top-level graph), this makes the nested-editing context visually
// explicit and gives it an obvious close affordance. z-40, one below the
// generic Modal's z-50, so CreateNodeDialog still layers correctly on top
// when creating a node from inside here.
export function LoopBodyModal({
  loopLabel,
  activeWorkflowId,
  nodes,
  edges,
  nodeCatalog,
  creatableNodeCatalog,
  selectedNode,
  selectedCount,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onAutoLayout,
  onSelectionChange,
  onNodesChange,
  onMoveNode,
  onConnect,
  onDeleteEdge,
  onDropNode,
  onDeleteNode,
  onAddNode,
  onSaveNode,
  onOpenCalledWorkflow,
  onClose,
}: LoopBodyModalProps) {
  const backdropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-40 flex flex-col gap-3 bg-[var(--bg)] p-4"
      onMouseDown={(event) => {
        if (event.target === backdropRef.current) {
          onClose()
        }
      }}
    >
      <div className="pixel-panel flex items-center justify-between gap-3 px-4 py-2">
        <div className="flex items-center gap-3">
          <button type="button" className="pixel-icon" title="Close (Esc)" onClick={onClose}>
            ✕ Close
          </button>
          <div className="font-pixel text-xs uppercase text-[var(--accent)]">
            Loop: {loopLabel}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="pixel-icon"
            disabled={!canUndo}
            title="Undo (Ctrl+Z)"
            onClick={onUndo}
          >
            Undo
          </button>
          <button
            type="button"
            className="pixel-icon"
            disabled={!canRedo}
            title="Redo (Ctrl+Shift+Z)"
            onClick={onRedo}
          >
            Redo
          </button>
          <button type="button" className="pixel-icon" title="Auto-layout" onClick={onAutoLayout}>
            Auto-layout
          </button>
        </div>
      </div>
      <div
        className={`grid flex-1 gap-3 overflow-hidden ${
          selectedNode ? 'grid-cols-[280px_1fr_320px]' : 'grid-cols-[280px_1fr]'
        }`}
      >
        <aside className="pixel-panel pixel-scroll overflow-y-auto">
          <NodePalette nodeCatalog={creatableNodeCatalog} onAddNode={onAddNode} />
        </aside>
        <GraphCanvas
          activeWorkflowId={activeWorkflowId}
          activeParentNodeId={null}
          nodes={nodes}
          edges={edges}
          nodeCatalog={nodeCatalog}
          runDisabledReason={null}
          selectedCount={selectedCount}
          onSelectionChange={onSelectionChange}
          onNodesChange={onNodesChange}
          onMoveNode={onMoveNode}
          onConnect={onConnect}
          onDeleteEdge={onDeleteEdge}
          onDropNode={onDropNode}
          onDeleteNode={onDeleteNode}
          onDrillIntoLoop={() => {}}
          onOpenCalledWorkflow={onOpenCalledWorkflow}
        />
        {selectedNode ? (
          <InspectorPanel
            node={selectedNode}
            nodeCatalog={nodeCatalog}
            currentWorkflowId={activeWorkflowId}
            onSaveNode={onSaveNode}
          />
        ) : null}
      </div>
    </div>
  )
}
