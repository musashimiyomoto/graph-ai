import { useState } from 'react'

import { useWorkflowTemplates } from '../hooks/useWorkflowTemplates'
import { Modal } from './Modal'

interface NewFromTemplateDialogProps {
  onCancel: () => void
  onConfirm: (templateKey: string) => Promise<void>
}

export function NewFromTemplateDialog({
  onCancel,
  onConfirm,
}: NewFromTemplateDialogProps) {
  const { templates, loading } = useWorkflowTemplates()
  const [creatingKey, setCreatingKey] = useState<string | null>(null)

  async function handleSelect(templateKey: string): Promise<void> {
    setCreatingKey(templateKey)
    try {
      await onConfirm(templateKey)
    } finally {
      setCreatingKey(null)
    }
  }

  return (
    <Modal onClose={onCancel} maxWidth="max-w-xl">
      <div className="pixel-section-title">New From Template</div>
      <div className="mt-4 flex flex-col gap-3">
        {loading ? (
          <div className="text-xs text-[var(--muted)]">Loading templates...</div>
        ) : templates.length === 0 ? (
          <div className="text-xs text-[var(--muted)]">No templates available.</div>
        ) : (
          templates.map((template) => (
            <div key={template.key} className="pixel-card items-start">
              <div className="flex-1">
                <div className="text-sm">{template.name}</div>
                <div className="mt-1 text-xs text-[var(--muted)]">
                  {template.description}
                </div>
              </div>
              <button
                type="button"
                className="pixel-button small"
                disabled={creatingKey !== null}
                onClick={() => void handleSelect(template.key)}
              >
                {creatingKey === template.key ? 'Creating...' : 'Use'}
              </button>
            </div>
          ))
        )}
      </div>

      <div className="mt-6 flex justify-end">
        <button
          type="button"
          className="pixel-button ghost"
          onClick={onCancel}
          disabled={creatingKey !== null}
        >
          Cancel
        </button>
      </div>
    </Modal>
  )
}
