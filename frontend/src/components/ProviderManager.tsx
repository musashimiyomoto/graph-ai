import { useEffect, useRef, useState } from 'react'

import type { ApiError } from '../lib/types'
import { useLlmProviders } from '../hooks/useLlmProviders'

interface ProviderManagerProps {
  onClose: () => void
  onError: (err: ApiError) => void
}

export function ProviderManager({ onClose, onError }: ProviderManagerProps) {
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  const {
    providers,
    creating,
    createProvider,
    removeProvider,
  } = useLlmProviders({
    onError,
  })

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
    try {
      const created = await createProvider({
        name: name.trim(),
        type: 'ollama',
        base_url: baseUrl.trim(),
        config: {},
      })
      if (created) {
        setName('')
        setBaseUrl('')
      }
    } catch (error) {
      onError(error as ApiError)
    }
  }

  async function handleDelete(providerId: number): Promise<void> {
    await removeProvider(providerId)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div
        ref={ref}
        className="pixel-panel modal-scroll w-full max-w-md max-h-[80vh] overflow-y-auto"
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
              Base URL
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
              disabled={creating || !name.trim() || !baseUrl.trim()}
              onClick={() => void handleCreate()}
            >
              {creating ? 'Saving...' : 'Add Provider'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
