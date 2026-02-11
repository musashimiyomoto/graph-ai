import { useMemo, useState } from 'react'

import type {
  LlmModel,
  LlmProvider,
  NodeCatalogItem,
  NodeCatalogField,
} from '../lib/types'
import { useLlmProviders } from '../hooks/useLlmProviders'
import { useProviderModels } from '../hooks/useProviderModels'

interface CreateNodeDialogProps {
  nodeSpec: NodeCatalogItem | null
  initialData: Record<string, unknown>
  onCancel: () => void
  onConfirm: (data: Record<string, unknown>) => Promise<void>
}

function TextField({
  value,
  placeholder,
  onChange,
}: {
  value: unknown
  placeholder: string | null
  onChange: (value: string) => void
}) {
  return (
    <input
      className="pixel-input"
      value={String(value ?? '')}
      placeholder={placeholder ?? ''}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

function TextAreaField({
  value,
  placeholder,
  onChange,
}: {
  value: unknown
  placeholder: string | null
  onChange: (value: string) => void
}) {
  return (
    <textarea
      className="pixel-textarea"
      value={String(value ?? '')}
      placeholder={placeholder ?? ''}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

function NumberField({
  field,
  value,
  onChange,
}: {
  field: NodeCatalogField
  value: unknown
  onChange: (value: number) => void
}) {
  return (
    <input
      className="pixel-input"
      type="number"
      value={Number(value ?? field.default ?? field.validators.ge ?? 0)}
      min={field.validators.ge}
      max={field.validators.le}
      step={0.1}
      onChange={(event) => onChange(Number(event.target.value))}
    />
  )
}

function SelectField({
  value,
  options,
  onChange,
}: {
  value: unknown
  options: string[]
  onChange: (value: string) => void
}) {
  return (
    <select
      className="pixel-input"
      value={String(value ?? options[0] ?? '')}
      onChange={(event) => onChange(event.target.value)}
    >
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  )
}

function ProviderField({
  providers,
  value,
  onChange,
}: {
  providers: LlmProvider[]
  value: unknown
  onChange: (value: number) => void
}) {
  return (
    <select
      className="pixel-input"
      value={String(value ?? '')}
      onChange={(event) => onChange(Number(event.target.value))}
    >
      <option value="">-- select provider --</option>
      {providers.map((provider) => (
        <option key={provider.id} value={provider.id}>
          {provider.name}
        </option>
      ))}
    </select>
  )
}

function ModelField({
  models,
  value,
  onChange,
}: {
  models: LlmModel[]
  value: unknown
  onChange: (value: string) => void
}) {
  return (
    <select
      className="pixel-input"
      value={String(value ?? '')}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">-- select model --</option>
      {models.map((model) => (
        <option key={model.name} value={model.name}>
          {model.name}
        </option>
      ))}
    </select>
  )
}

export function CreateNodeDialog({
  nodeSpec,
  initialData,
  onCancel,
  onConfirm,
}: CreateNodeDialogProps) {
  const [data, setData] = useState<Record<string, unknown>>(initialData)
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const fields = useMemo(() => nodeSpec?.fields ?? [], [nodeSpec])
  const hasProviderDatasource = fields.some(
    (field) => field.datasource?.kind === 'llm_provider',
  )
  const hasModelDatasource = fields.some(
    (field) => field.datasource?.kind === 'llm_model',
  )

  const selectedProviderRaw = Number(data['llm_provider_id'] ?? 0)
  const selectedProviderId =
    Number.isInteger(selectedProviderRaw) && selectedProviderRaw > 0
      ? selectedProviderRaw
      : null

  const { providers } = useLlmProviders({
    enabled: hasProviderDatasource,
  })
  const { models } = useProviderModels({
    providerId: selectedProviderId,
    enabled: hasModelDatasource,
  })

  const validationErrors = useMemo(() => {
    const nextErrors: Record<string, string> = {}

    for (const field of fields) {
      if (!field.required) {
        continue
      }

      const value = data[field.name]
      if (field.ui.widget === 'number') {
        if (typeof value !== 'number' || Number.isNaN(value)) {
          nextErrors[field.name] = `${field.ui.label} is required`
        }
        continue
      }

      if (field.ui.widget === 'provider') {
        if (!Number.isInteger(Number(value)) || Number(value) <= 0) {
          nextErrors[field.name] = `${field.ui.label} is required`
        }
        continue
      }

      if (String(value ?? '').trim().length === 0) {
        nextErrors[field.name] = `${field.ui.label} is required`
      }
    }

    return nextErrors
  }, [data, fields])

  function updateField(name: string, value: string | number) {
    setData((previous) => ({ ...previous, [name]: value }))
    setErrors((previous) => {
      if (!(name in previous)) {
        return previous
      }
      const { [name]: _removed, ...rest } = previous
      void _removed
      return rest
    })
  }

  function renderField(field: NodeCatalogField) {
    const value = data[field.name]

    if (field.ui.widget === 'provider') {
      return (
        <ProviderField
          providers={providers}
          value={value}
          onChange={(providerId) => {
            updateField(field.name, providerId)
            updateField('model', '')
          }}
        />
      )
    }

    if (field.ui.widget === 'model') {
      return (
        <ModelField
          models={models}
          value={value}
          onChange={(model) => updateField(field.name, model)}
        />
      )
    }

    if (field.ui.widget === 'select') {
      return (
        <SelectField
          value={value}
          options={field.validators.select ?? []}
          onChange={(selected) => updateField(field.name, selected)}
        />
      )
    }

    if (field.ui.widget === 'number') {
      return (
        <NumberField
          field={field}
          value={value}
          onChange={(numberValue) => updateField(field.name, numberValue)}
        />
      )
    }

    if (field.ui.widget === 'textarea') {
      return (
        <TextAreaField
          value={value}
          placeholder={field.ui.placeholder}
          onChange={(text) => updateField(field.name, text)}
        />
      )
    }

    return (
      <TextField
        value={value}
        placeholder={field.ui.placeholder}
        onChange={(text) => updateField(field.name, text)}
      />
    )
  }

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="pixel-panel modal-scroll max-h-[80vh] w-full max-w-xl overflow-y-auto">
        <div className="pixel-section-title">Create {nodeSpec.label} Node</div>
        <div className="mt-4 flex flex-col gap-3">
          {fields.map((field) => (
            <label key={field.name} className="pixel-label">
              {field.ui.label}
              {renderField(field)}
              {errors[field.name] ? (
                <span className="text-xs text-red-300">{errors[field.name]}</span>
              ) : null}
              {field.ui.help ? (
                <span className="text-xs text-[var(--muted)]">{field.ui.help}</span>
              ) : null}
            </label>
          ))}
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
      </div>
    </div>
  )
}
