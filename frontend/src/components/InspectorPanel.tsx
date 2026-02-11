import { useEffect, useMemo, useRef, useState } from 'react'
import type { Node as FlowNode } from 'reactflow'

import { getLlmProviderModels, getLlmProviders } from '../lib/api'
import type {
  LlmModel,
  LlmProvider,
  NodeCatalogItem,
  NodeCatalogField,
  NodeType,
} from '../lib/types'

interface InspectorPanelProps {
  node: FlowNode | null
  nodeCatalog: NodeCatalogItem[]
  onSaveNode: (id: string, data: Record<string, unknown>) => void
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
      onChange={(event) => onChange(Number(event.target.value))}
      min={field.validators.ge}
      max={field.validators.le}
      step={0.1}
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

export function InspectorPanel({
  node,
  nodeCatalog,
  onSaveNode,
}: InspectorPanelProps) {
  const nodeType = (node?.data?.nodeType as NodeType | undefined) ?? null
  const [providers, setProviders] = useState<LlmProvider[]>([])
  const [models, setModels] = useState<LlmModel[]>([])
  const [draftData, setDraftData] = useState<Record<string, unknown>>({})
  const lastSavedSnapshotRef = useRef<string>('')

  const catalogByType = useMemo(
    () => Object.fromEntries(nodeCatalog.map((item) => [item.type, item])) as Record<string, NodeCatalogItem>,
    [nodeCatalog],
  )

  const nodeSpec = nodeType ? catalogByType[nodeType] : undefined
  const fields = useMemo(() => nodeSpec?.fields ?? [], [nodeSpec])
  const allowedFieldNames = useMemo(
    () => new Set(fields.map((field) => field.name)),
    [fields],
  )

  const hasProviderDatasource = fields.some(
    (field) => field.datasource?.kind === 'llm_provider',
  )
  const hasModelDatasource = fields.some(
    (field) => field.datasource?.kind === 'llm_model',
  )

  const selectedProviderId = Number(draftData['llm_provider_id'] ?? 0)

  useEffect(() => {
    let cancelled = false
    const rawData = node ? ((node.data as Record<string, unknown>) ?? {}) : {}
    const initialData = node
      ? Object.fromEntries(
          Object.entries(rawData).filter(([key]) => allowedFieldNames.has(key)),
        )
      : {}
    const snapshot = node ? JSON.stringify(initialData) : ''

    void Promise.resolve().then(() => {
      if (cancelled) {
        return
      }
      setDraftData(initialData)
      lastSavedSnapshotRef.current = snapshot
    })

    return () => {
      cancelled = true
    }
  }, [allowedFieldNames, node])

  useEffect(() => {
    if (!node) {
      return
    }

    const snapshot = JSON.stringify(draftData)
    if (snapshot === lastSavedSnapshotRef.current) {
      return
    }

    const timer = window.setTimeout(() => {
      lastSavedSnapshotRef.current = snapshot
      onSaveNode(node.id, draftData)
    }, 400)

    return () => window.clearTimeout(timer)
  }, [draftData, node, onSaveNode])

  useEffect(() => {
    let cancelled = false

    if (!hasProviderDatasource) {
      void Promise.resolve().then(() => {
        if (!cancelled) {
          setProviders([])
        }
      })
      return () => { cancelled = true }
    }

    void getLlmProviders()
      .then((data) => {
        if (!cancelled) {
          setProviders(data)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProviders([])
        }
      })

    return () => { cancelled = true }
  }, [hasProviderDatasource])

  useEffect(() => {
    let cancelled = false

    if (!hasModelDatasource || !selectedProviderId) {
      void Promise.resolve().then(() => {
        if (!cancelled) {
          setModels([])
        }
      })
      return () => { cancelled = true }
    }

    void getLlmProviderModels(selectedProviderId)
      .then((data) => {
        if (!cancelled) {
          setModels(data)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setModels([])
        }
      })

    return () => { cancelled = true }
  }, [hasModelDatasource, selectedProviderId])

  function updateField(key: string, value: string | number) {
    setDraftData((current) => ({ ...current, [key]: value }))
  }

  function renderField(field: NodeCatalogField) {
    const value = draftData[field.name]

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

  return (
    <aside className="pixel-panel flex h-full flex-col gap-6">
      <div>
        <div className="pixel-section-title">Inspector</div>
        {!node ? (
          <div className="mt-4 text-xs text-[var(--muted)]">
            Select a node to configure its parameters.
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-3">
            <div className="text-xs text-[var(--muted)]">
              Type: <span className="text-[var(--accent)]">{nodeType}</span>
            </div>
            {fields.map((field) => (
              <label key={field.name} className="pixel-label">
                {field.ui.label}
                {renderField(field)}
                {field.ui.help ? (
                  <span className="text-xs text-[var(--muted)]">{field.ui.help}</span>
                ) : null}
              </label>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
