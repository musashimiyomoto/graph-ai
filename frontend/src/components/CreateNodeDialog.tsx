import { useMemo, useState } from 'react'

import type { NodeCatalogItem } from '../lib/types'
import { validateFields } from '../lib/validation'
import { Modal } from './Modal'
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
    <Modal onClose={onCancel} maxWidth="max-w-xl">
      <div className="pixel-section-title">Create {nodeSpec.label} Node</div>
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
    </Modal>
  )
}
