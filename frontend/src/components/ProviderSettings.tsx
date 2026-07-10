import { useState } from 'react'

import type { ApiError } from '../lib/types'
import { useLlmProviders } from '../hooks/useLlmProviders'
import { OllamaModelsPanel } from './OllamaModelsPanel'

interface ProviderSettingsProps {
  onError: (err: ApiError) => void
}

type ProviderType = 'ollama' | 'openai' | 'anthropic' | 'openai_compatible'

interface ProviderTypeSpec {
  label: string
  defaultBaseUrl: string
  requiresApiKey: boolean
}

const PROVIDER_TYPES: Record<ProviderType, ProviderTypeSpec> = {
  ollama: {
    label: 'Ollama',
    defaultBaseUrl: 'http://localhost:11434',
    requiresApiKey: false,
  },
  openai: {
    label: 'OpenAI',
    defaultBaseUrl: 'https://api.openai.com/v1',
    requiresApiKey: true,
  },
  anthropic: {
    label: 'Anthropic',
    defaultBaseUrl: 'https://api.anthropic.com',
    requiresApiKey: true,
  },
  openai_compatible: {
    label: 'OpenAI-compatible',
    defaultBaseUrl: '',
    requiresApiKey: true,
  },
}

const PROVIDER_TYPE_ORDER: ProviderType[] = [
  'ollama',
  'openai',
  'anthropic',
  'openai_compatible',
]

export function ProviderSettings({ onError }: ProviderSettingsProps) {
  const [name, setName] = useState('')
  const [type, setType] = useState<ProviderType>('ollama')
  const [baseUrl, setBaseUrl] = useState(PROVIDER_TYPES.ollama.defaultBaseUrl)
  const [baseUrlTouched, setBaseUrlTouched] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [expandedProviderId, setExpandedProviderId] = useState<number | null>(null)

  const spec = PROVIDER_TYPES[type]
  const apiKeyMissing = spec.requiresApiKey && !apiKey.trim()
  const {
    providers,
    creating,
    createProvider,
    removeProvider,
  } = useLlmProviders({
    onError,
  })

  function handleTypeChange(nextType: ProviderType): void {
    setType(nextType)
    if (!baseUrlTouched) {
      setBaseUrl(PROVIDER_TYPES[nextType].defaultBaseUrl)
    }
    if (!PROVIDER_TYPES[nextType].requiresApiKey) {
      setApiKey('')
    }
  }

  async function handleCreate(): Promise<void> {
    try {
      const created = await createProvider({
        name: name.trim(),
        type,
        base_url: baseUrl.trim(),
        config: {},
        api_key: spec.requiresApiKey ? apiKey.trim() : null,
      })
      if (created) {
        setName('')
        setType('ollama')
        setBaseUrl(PROVIDER_TYPES.ollama.defaultBaseUrl)
        setBaseUrlTouched(false)
        setApiKey('')
      }
    } catch (error) {
      onError(error as ApiError)
    }
  }

  async function handleDelete(providerId: number): Promise<void> {
    await removeProvider(providerId)
    setConfirmDeleteId(null)
    if (expandedProviderId === providerId) {
      setExpandedProviderId(null)
    }
  }

  function toggleExpanded(providerId: number): void {
    setExpandedProviderId((current) =>
      current === providerId ? null : providerId,
    )
  }

  return (
    <div>
      <div className="flex flex-col gap-3">
        {providers.length === 0 ? (
          <div className="text-xs text-[var(--muted)]">
            No providers yet.
          </div>
        ) : null}
        {providers.map((provider) => (
          <div key={provider.id} className="flex flex-col gap-2">
            <div className="pixel-card">
              <div className="flex-1">
                <div className="text-sm">{provider.name}</div>
                <div className="text-xs text-[var(--muted)]">
                  {provider.type}
                  {provider.base_url ? ` · ${provider.base_url}` : ''}
                </div>
              </div>
              {provider.type === 'ollama' ? (
                <button
                  type="button"
                  className="pixel-icon"
                  title="Manage models"
                  onClick={() => toggleExpanded(provider.id)}
                >
                  Models
                </button>
              ) : null}
              {confirmDeleteId === provider.id ? (
                <>
                  <button
                    type="button"
                    className="pixel-icon danger"
                    title="Confirm delete"
                    onClick={() => void handleDelete(provider.id)}
                  >
                    ✓
                  </button>
                  <button
                    type="button"
                    className="pixel-icon"
                    title="Cancel"
                    onClick={() => setConfirmDeleteId(null)}
                  >
                    ✕
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="pixel-icon danger"
                  onClick={() => setConfirmDeleteId(provider.id)}
                >
                  Del
                </button>
              )}
            </div>
            {provider.type === 'ollama' && expandedProviderId === provider.id ? (
              <div className="ml-4 border-l border-white/10 pl-4">
                <OllamaModelsPanel providerId={provider.id} onError={onError} />
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <div className="mt-6 border-t border-white/10 pt-4">
        <div className="mb-3 text-xs uppercase tracking-widest text-[var(--muted)]">
          Add provider
        </div>
        <div className="flex flex-col gap-3">
          <label className="pixel-label">
            Name
            <input
              className="pixel-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Provider"
            />
          </label>
          <label className="pixel-label">
            Type
            <select
              className="pixel-input"
              value={type}
              onChange={(e) => handleTypeChange(e.target.value as ProviderType)}
            >
              {PROVIDER_TYPE_ORDER.map((option) => (
                <option key={option} value={option}>
                  {PROVIDER_TYPES[option].label}
                </option>
              ))}
            </select>
          </label>
          <label className="pixel-label">
            Base URL
            <input
              className="pixel-input"
              value={baseUrl}
              onChange={(e) => {
                setBaseUrl(e.target.value)
                setBaseUrlTouched(true)
              }}
              placeholder={spec.defaultBaseUrl || 'https://api.example.com/v1'}
            />
          </label>
          {spec.requiresApiKey ? (
            <label className="pixel-label">
              API Key
              <input
                className="pixel-input"
                type="password"
                value={apiKey}
                autoComplete="off"
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
              />
            </label>
          ) : null}
          <button
            type="button"
            className="pixel-button small"
            disabled={creating || !name.trim() || !baseUrl.trim() || apiKeyMissing}
            onClick={() => void handleCreate()}
          >
            {creating ? 'Saving...' : 'Add Provider'}
          </button>
        </div>
      </div>
    </div>
  )
}
