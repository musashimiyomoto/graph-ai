import type { Edge, Node as FlowNode, NodeChange } from 'reactflow'

import type { NodeCatalogItem, NodeType, PortCoercion } from '../lib/types'
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
  onConnect: (
    sourceId: string,
    targetId: string,
    sourceHandle: string | null,
    targetHandle: string | null,
    coercion: PortCoercion | null,
  ) => void
  onDeleteEdge: (edgeId: string) => void
  onDropNode: (type: string, position: { x: number; y: number }) => void
  onDeleteNode: (id: string) => void
  onAddNode: (type: NodeType) => void
  onSaveNode: (id: string, data: Record<string, unknown>) => Promise<boolean>
  onOpenCalledWorkflow: (workflowId: number) => void
  onClose: () => void
}

// Inline workspace for a Loop body. The persistent scope header and explicit
// back action keep the nested context clear without covering the application.
export function LoopBodyModal({
  loopNodeId,
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
  return (
    <>
      <aside className="pixel-panel pixel-scroll overflow-y-auto">
        <div className="border-b border-white/10 p-3">
          <button type="button" className="pixel-button ghost small w-full" onClick={onClose}>
            ← Workflow graph
          </button>
          <div className="mt-3 text-xs uppercase tracking-wider text-[var(--accent)]">
            Loop: {loopLabel}
          </div>
        </div>
        <NodePalette nodeCatalog={creatableNodeCatalog} onAddNode={onAddNode} />
      </aside>
      <section className="flex min-w-0 flex-col gap-3 overflow-hidden">
        <div className="pixel-panel flex items-center justify-between gap-3 px-4 py-2">
          <div className="text-sm text-[var(--muted)]">Editing loop body</div>
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
            <button
              type="button"
              className="pixel-icon"
              title="Auto-layout"
              onClick={onAutoLayout}
            >
              Auto-layout
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1">
        <GraphCanvas
          activeWorkflowId={activeWorkflowId}
          activeParentNodeId={loopNodeId}
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
        </div>
      </section>
      {selectedNode ? (
        <InspectorPanel
          node={selectedNode}
          nodeCatalog={nodeCatalog}
          currentWorkflowId={activeWorkflowId}
          onSaveNode={onSaveNode}
        />
      ) : null}
    </>
  )
}
