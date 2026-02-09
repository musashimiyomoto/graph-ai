import { useEffect, useState } from 'react'
import type { Node as FlowNode } from 'reactflow'

import { getLlmProviderModels, getLlmProviders, getNodeFields } from '../lib/api'
import type {
  LlmModel,
  LlmProvider,
  NodeField,
  NodeType,
} from '../lib/types'

interface InspectorPanelProps {
  node: FlowNode | null
  onSaveNode: (id: string, data: Record<string, unknown>) => void
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: NodeField
  value: unknown
  onChange: (value: string | number) => void
}) {
  const { validators } = field

  if (validators.select) {
    return (
      <select
        className="pixel-input"
        value={String(value ?? validators.select[0] ?? '')}
        onChange={(event) => onChange(event.target.value)}
      >
        {validators.select.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    )
  }

  if (validators.ge !== undefined || validators.le !== undefined) {
    return (
      <input
        className="pixel-input"
        type="number"
        value={Number(value ?? validators.ge ?? 0)}
        onChange={(event) => onChange(Number(event.target.value))}
        min={validators.ge}
        max={validators.le}
        step={0.1}
      />
    )
  }

  if (field.name.includes('prompt')) {
    return (
      <textarea
        className="pixel-textarea"
        value={String(value ?? '')}
        onChange={(event) => onChange(event.target.value)}
      />
    )
  }

  return (
    <input
      className="pixel-input"
      value={String(value ?? '')}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

function ProviderSelect({
  providers,
  value,
  onChange,
}: {
  providers: LlmProvider[]
  value: unknown
  onChange: (value: string) => void
}) {
  return (
    <select
      className="pixel-input"
      value={String(value ?? '')}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">-- select provider --</option>
      {providers.map((provider) => (
        <option key={provider.id} value={provider.name}>
          {provider.name}
        </option>
      ))}
    </select>
  )
}

function ModelSelect({
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
  onSaveNode,
}: InspectorPanelProps) {
  const nodeType = (node?.data?.nodeType as NodeType | undefined) ?? null
  const nodeData = (node?.data as Record<string, unknown>) ?? {}
  const [fields, setFields] = useState<NodeField[]>([])
  const [providers, setProviders] = useState<LlmProvider[]>([])
  const [models, setModels] = useState<LlmModel[]>([])

  useEffect(() => {
    let cancelled = false
    if (!nodeType) {
      void Promise.resolve().then(() => {
        if (!cancelled) setFields([])
      })
      return () => { cancelled = true }
    }
    void getNodeFields(nodeType)
      .then((data) => { if (!cancelled) setFields(data) })
      .catch(() => { if (!cancelled) setFields([]) })
    return () => { cancelled = true }
  }, [nodeType])

  useEffect(() => {
    let cancelled = false
    if (nodeType !== 'llm') {
      void Promise.resolve().then(() => {
        if (!cancelled) setProviders([])
      })
      return () => { cancelled = true }
    }
    void getLlmProviders()
      .then((data) => { if (!cancelled) setProviders(data) })
      .catch(() => { if (!cancelled) setProviders([]) })
    return () => { cancelled = true }
  }, [nodeType])

  const selectedProviderName = String(nodeData['llm_provider'] ?? '')
  const selectedProvider = providers.find((p) => p.name === selectedProviderName)

  useEffect(() => {
    let cancelled = false
    if (!selectedProvider) {
      void Promise.resolve().then(() => {
        if (!cancelled) setModels([])
      })
      return () => { cancelled = true }
    }
    void getLlmProviderModels(selectedProvider.id)
      .then((data) => { if (!cancelled) setModels(data) })
      .catch(() => { if (!cancelled) setModels([]) })
    return () => { cancelled = true }
  }, [selectedProvider])

  function updateField(key: string, value: string | number) {
    if (!node) {
      return
    }
    const updated = { ...nodeData, [key]: value }
    onSaveNode(node.id, updated)
  }

  function handleProviderChange(providerName: string) {
    if (!node) {
      return
    }
    const updated = { ...nodeData, llm_provider: providerName, model: '' }
    onSaveNode(node.id, updated)
  }

  function renderField(field: NodeField) {
    if (field.name === 'llm_provider') {
      return (
        <ProviderSelect
          providers={providers}
          value={nodeData[field.name]}
          onChange={handleProviderChange}
        />
      )
    }

    if (field.name === 'model') {
      return (
        <ModelSelect
          models={models}
          value={nodeData[field.name]}
          onChange={(value) => updateField(field.name, value)}
        />
      )
    }

    return (
      <FieldInput
        field={field}
        value={nodeData[field.name]}
        onChange={(value) => updateField(field.name, value)}
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
                {field.name.replace(/_/g, ' ')}
                {renderField(field)}
              </label>
            ))}
          </div>
        )}
      </div>


    </aside>
  )
}
