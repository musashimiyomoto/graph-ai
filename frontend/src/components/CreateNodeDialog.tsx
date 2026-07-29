import { useMemo, useState } from 'react'

import type { NodeCatalogItem } from '../lib/types'
import { validateFields } from '../lib/validation'
import { NodeFieldsForm } from './NodeFieldsForm'

interface CreateNodeDialogProps {
  nodeSpec: NodeCatalogItem | null
  initialData: Record<string, unknown>
  currentWorkflowId: number | null
  onCancel: () => void
  onConfirm: (data: Record<string, unknown>) => Promise<void>
}

export function CreateNodeDialog({
  nodeSpec,
  initialData,
  currentWorkflowId,
  onCancel,
  onConfirm,
}: CreateNodeDialogProps) {
  const [data, setData] = useState<Record<string, unknown>>(initialData)
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const fields = useMemo(() => nodeSpec?.fields ?? [], [nodeSpec])
  const validationErrors = useMemo(() => validateFields(fields, data), [data, fields])

  async function submit() {
    if (!nodeSpec) {
      return
    }

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors)
      return
    }

    setSubmitting(true)
    try {
      await onConfirm(data)
    } finally {
      setSubmitting(false)
    }
  }

  if (!nodeSpec) {
    return null
  }

  return (
    <aside className="pixel-panel pixel-scroll overflow-y-auto p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="pixel-section-title">Create node</div>
          <div className="mt-2 text-lg text-[var(--text)]">{nodeSpec.label}</div>
        </div>
        <button
          type="button"
          className="pixel-icon"
          aria-label="Cancel node creation"
          disabled={submitting}
          onClick={onCancel}
        >
          ✕
        </button>
      </div>
      <div className="mt-4 flex flex-col gap-3">
        <NodeFieldsForm
          fields={fields}
          data={data}
          errors={errors}
          currentWorkflowId={currentWorkflowId}
          onFieldChange={(name, next) => {
            setData(next)
            setErrors((previous) => {
              if (!(name in previous)) {
                return previous
              }
              const { [name]: _removed, ...rest } = previous
              void _removed
              return rest
            })
          }}
        />
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <button
          type="button"
          className="pixel-button ghost"
          onClick={onCancel}
          disabled={submitting}
        >
          Cancel
        </button>
        <button
          type="button"
          className="pixel-button"
          onClick={() => {
            void submit()
          }}
          disabled={submitting}
        >
          {submitting ? 'Creating...' : 'Create'}
        </button>
      </div>
    </aside>
  )
}
