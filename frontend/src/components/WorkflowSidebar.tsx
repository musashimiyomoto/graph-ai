import { useState } from 'react'

import type { NodeType, Workflow } from '../lib/types'

interface WorkflowSidebarProps {
  workflows: Workflow[]
  activeWorkflowId: number | null
  onSelectWorkflow: (id: number) => void
  onCreateWorkflow: (name: string) => void
  onRenameWorkflow: (id: number, name: string) => void
  onDeleteWorkflow: (id: number) => void
  onAddNode: (type: NodeType) => void
}

export function WorkflowSidebar({
  workflows,
  activeWorkflowId,
  onSelectWorkflow,
  onCreateWorkflow,
  onRenameWorkflow,
  onDeleteWorkflow,
  onAddNode,
}: WorkflowSidebarProps) {
  const [draftName, setDraftName] = useState('')

  return (
    <aside className="pixel-panel flex h-full flex-col gap-6">
      <div>
        <div className="pixel-section-title">Workflows</div>
        <div className="mt-3 flex gap-2">
          <input
            className="pixel-input"
            placeholder="New workflow"
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
          />
          <button
            type="button"
            className="pixel-button small"
            onClick={() => {
              onCreateWorkflow(draftName)
              setDraftName('')
            }}
          >
            Add
          </button>
        </div>
        <div className="mt-4 flex flex-col gap-2">
          {workflows.length === 0 ? (
            <div className="text-xs text-[var(--muted)]">
              Пока нет workflows. Создай первый.
            </div>
          ) : null}
          {workflows.map((workflow) => (
            <div
              key={workflow.id}
              className={`pixel-card ${workflow.id === activeWorkflowId ? 'is-active' : ''}`}
            >
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
                onClick={() =>
                  onRenameWorkflow(
                    workflow.id,
                    window.prompt('Rename workflow', workflow.name) ?? workflow.name,
                  )
                }
              >
                Edit
              </button>
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
          {(['INPUT', 'LLM', 'OUTPUT'] as NodeType[]).map((type) => (
            <button
              key={type}
              type="button"
              className="pixel-button ghost"
              onClick={() => onAddNode(type)}
            >
              + {type}
            </button>
          ))}
        </div>
      </div>
    </aside>
  )
}
