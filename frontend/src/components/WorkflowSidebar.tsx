import { useEffect, useRef, useState } from 'react'

import { STATUS_DOT_COLORS } from '../lib/executionFormat'
import type { ExecutionStatus, NodeCatalogItem, NodeType, Workflow } from '../lib/types'
import { NodePalette } from './NodePalette'
import { WorkflowActionsMenu } from './WorkflowActionsMenu'

interface WorkflowSidebarProps {
  workflows: Workflow[]
  activeWorkflowId: number | null
  activeWorkflowStatus: ExecutionStatus | null
  nodeCatalog: NodeCatalogItem[]
  onSelectWorkflow: (id: number) => void
  onCreateWorkflow: (name: string) => void
  onRenameWorkflow: (id: number, name: string) => void
  onDeleteWorkflow: (id: number) => void
  onDuplicateWorkflow: (id: number) => void
  onExportWorkflow: (id: number) => void
  onCopyWebhook: (workflow: Workflow) => Promise<boolean>
  onImportWorkflow: (file: File) => void
  onOpenNewFromTemplate: () => void
  onAddNode: (type: NodeType) => void
}

export function WorkflowSidebar({
  workflows,
  activeWorkflowId,
  activeWorkflowStatus,
  nodeCatalog,
  onSelectWorkflow,
  onCreateWorkflow,
  onRenameWorkflow,
  onDeleteWorkflow,
  onDuplicateWorkflow,
  onExportWorkflow,
  onCopyWebhook,
  onImportWorkflow,
  onOpenNewFromTemplate,
  onAddNode,
}: WorkflowSidebarProps) {
  const [draftName, setDraftName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')
  const editRef = useRef<HTMLInputElement>(null)
  const importInputRef = useRef<HTMLInputElement>(null)

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
    <aside className="pixel-panel pixel-scroll flex h-full flex-col gap-6 overflow-y-auto">
      <div>
        <div className="pixel-section-title">Workflows</div>
        <div className="mt-3 flex gap-2">
          <input
            className="pixel-input flex-1"
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
        <input
          ref={importInputRef}
          type="file"
          accept="application/json"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) {
              onImportWorkflow(file)
            }
            event.target.value = ''
          }}
        />
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            className="pixel-button ghost small flex-1"
            title="Import a workflow from an exported JSON file"
            onClick={() => importInputRef.current?.click()}
          >
            Import
          </button>
          <button
            type="button"
            className="pixel-button ghost small flex-1"
            onClick={onOpenNewFromTemplate}
          >
            From Template
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
                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                    onClick={() => onSelectWorkflow(workflow.id)}
                  >
                    {workflow.id === activeWorkflowId && activeWorkflowStatus ? (
                      <span
                        className={`h-2 w-2 shrink-0 rounded-full ${STATUS_DOT_COLORS[activeWorkflowStatus]} ${activeWorkflowStatus === 'running' ? 'animate-pulse' : ''}`}
                        title={`Status: ${activeWorkflowStatus}`}
                      />
                    ) : null}
                    <span className="truncate">{workflow.name}</span>
                  </button>
                  <div className="shrink-0">
                    <WorkflowActionsMenu
                      onEdit={() => startEditing(workflow)}
                      onDuplicate={() => onDuplicateWorkflow(workflow.id)}
                      onExport={() => onExportWorkflow(workflow.id)}
                      onCopyWebhook={() => onCopyWebhook(workflow)}
                      onDelete={() => onDeleteWorkflow(workflow.id)}
                    />
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      <NodePalette nodeCatalog={nodeCatalog} onAddNode={onAddNode} />
    </aside>
  )
}
