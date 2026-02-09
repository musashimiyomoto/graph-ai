import { useEffect, useRef, useState } from 'react'

import {
  createLlmProvider,
  deleteLlmProvider,
  getLlmProviders,
} from '../lib/api'
import type { ApiError, LlmProvider } from '../lib/types'

interface ProviderManagerProps {
  onClose: () => void
  onError: (err: ApiError) => void
}

export function ProviderManager({ onClose, onError }: ProviderManagerProps) {
  const [providers, setProviders] = useState<LlmProvider[]>([])
  const [name, setName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [saving, setSaving] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    void getLlmProviders()
      .then((data) => {
        if (!cancelled) setProviders(data)
      })
      .catch((err: ApiError) => onError(err))
    return () => {
      cancelled = true
    }
  }, [onError])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as HTMLElement)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  async function handleCreate(): Promise<void> {
    if (!name.trim() || !apiKey.trim()) {
      return
    }
    setSaving(true)
    try {
      const created = await createLlmProvider({
        name: name.trim(),
        type: 'ollama',
        api_key: apiKey.trim(),
        base_url: baseUrl.trim() || undefined,
      })
      setProviders((prev) => [...prev, created])
      setName('')
      setApiKey('')
      setBaseUrl('')
    } catch (err) {
      onError(err as ApiError)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(providerId: number): Promise<void> {
    try {
      await deleteLlmProvider(providerId)
      setProviders((prev) => prev.filter((p) => p.id !== providerId))
    } catch (err) {
      onError(err as ApiError)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div
        ref={ref}
        className="pixel-panel w-full max-w-md max-h-[80vh] overflow-y-auto"
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="pixel-section-title">LLM Providers</div>
          <button
            type="button"
            className="pixel-icon"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <div className="flex flex-col gap-3">
          {providers.length === 0 ? (
            <div className="text-xs text-[var(--muted)]">
              No providers yet.
            </div>
          ) : null}
          {providers.map((provider) => (
            <div key={provider.id} className="pixel-card">
              <div className="flex-1">
                <div className="text-sm">{provider.name}</div>
                <div className="text-xs text-[var(--muted)]">
                  {provider.type}
                  {provider.base_url ? ` · ${provider.base_url}` : ''}
                </div>
              </div>
              <button
                type="button"
                className="pixel-icon danger"
                onClick={() => void handleDelete(provider.id)}
              >
                Del
              </button>
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
                placeholder="My Ollama"
              />
            </label>
            <label className="pixel-label">
              API Key
              <input
                className="pixel-input"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
              />
            </label>
            <label className="pixel-label">
              Base URL (optional)
              <input
                className="pixel-input"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost:11434"
              />
            </label>
            <button
              type="button"
              className="pixel-button small"
              disabled={saving || !name.trim() || !apiKey.trim()}
              onClick={() => void handleCreate()}
            >
              {saving ? 'Saving...' : 'Add Provider'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
