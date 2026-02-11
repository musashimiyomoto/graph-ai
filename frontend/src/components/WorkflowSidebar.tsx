import { useEffect, useRef, useState } from 'react'

import type { NodeCatalogItem, NodeType, Workflow } from '../lib/types'
import { NodeIcon } from './NodeIcons'

interface WorkflowSidebarProps {
  workflows: Workflow[]
  activeWorkflowId: number | null
  nodeCatalog: NodeCatalogItem[]
  onSelectWorkflow: (id: number) => void
  onCreateWorkflow: (name: string) => void
  onRenameWorkflow: (id: number, name: string) => void
  onDeleteWorkflow: (id: number) => void
  onAddNode: (type: NodeType) => void
}

export function WorkflowSidebar({
  workflows,
  activeWorkflowId,
  nodeCatalog,
  onSelectWorkflow,
  onCreateWorkflow,
  onRenameWorkflow,
  onDeleteWorkflow,
  onAddNode,
}: WorkflowSidebarProps) {
  const [draftName, setDraftName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')
  const editRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editingId !== null) {
      editRef.current?.focus()
      editRef.current?.select()
    }
  }, [editingId])

  function startEditing(workflow: Workflow) {
    setEditingId(workflow.id)
    setEditingName(workflow.name)
  }

  function commitEdit() {
    if (editingId !== null && editingName.trim()) {
      onRenameWorkflow(editingId, editingName.trim())
    }
    setEditingId(null)
  }

  function cancelEdit() {
    setEditingId(null)
  }

  return (
    <aside className="pixel-panel flex h-full flex-col gap-6 overflow-y-auto">
      <div>
        <div className="pixel-section-title">Workflows</div>
        <div className="mt-3 flex gap-2">
          <input
            className="pixel-input"
            placeholder="New workflow"
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && draftName.trim()) {
                onCreateWorkflow(draftName)
                setDraftName('')
              }
            }}
          />
          <button
            type="button"
            className="pixel-button small"
            onClick={() => {
              if (draftName.trim()) {
                onCreateWorkflow(draftName)
                setDraftName('')
              }
            }}
          >
            Add
          </button>
        </div>
        <div className="mt-4 flex flex-col gap-2">
          {workflows.length === 0 ? (
            <div className="text-xs text-[var(--muted)]">
              No workflows yet. Create your first one.
            </div>
          ) : null}
          {workflows.map((workflow) => (
            <div
              key={workflow.id}
              className={`pixel-card ${workflow.id === activeWorkflowId ? 'is-active' : ''}`}
            >
              {editingId === workflow.id ? (
                <input
                  ref={editRef}
                  className="pixel-input flex-1"
                  value={editingName}
                  onChange={(event) => setEditingName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      commitEdit()
                    }
                    if (event.key === 'Escape') {
                      cancelEdit()
                    }
                  }}
                  onBlur={commitEdit}
                />
              ) : (
                <>
                  <button
                    type="button"
                    className="flex-1 text-left"
                    onClick={() => onSelectWorkflow(workflow.id)}
                  >
                    {workflow.name}
                  </button>
                  <button
                    type="button"
                    className="pixel-icon"
                    onClick={() => startEditing(workflow)}
                  >
                    Edit
                  </button>
                </>
              )}
              <button
                type="button"
                className="pixel-icon danger"
                onClick={() => onDeleteWorkflow(workflow.id)}
              >
                Del
              </button>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="pixel-section-title">Nodes</div>
        <div className="mt-3 grid grid-cols-1 gap-2">
          {nodeCatalog.map((catalogNode) => {
            return (
              <button
                key={catalogNode.type}
                type="button"
                className="pixel-button ghost flex items-center gap-2"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData(
                    'application/graphai-node-type',
                    catalogNode.type,
                  )
                  event.dataTransfer.effectAllowed = 'move'
                }}
                onClick={() => onAddNode(catalogNode.type)}
              >
                <NodeIcon iconKey={catalogNode.icon_key} /> {catalogNode.label}
              </button>
            )
          })}
        </div>
      </div>
    </aside>
  )
}
