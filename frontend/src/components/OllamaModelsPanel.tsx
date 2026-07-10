import { useCallback, useEffect, useState } from 'react'

import {
  deleteProviderModel,
  getLlmProviderModels,
  getOllamaCatalog,
} from '../lib/api'
import { useOllamaPull } from '../hooks/useOllamaPull'
import type { ApiError, LlmModel, OllamaCatalogEntry } from '../lib/types'
import { OllamaModelPicker } from './OllamaModelPicker'

interface OllamaModelsPanelProps {
  providerId: number
  onError: (error: ApiError) => void
}

export function OllamaModelsPanel({ providerId, onError }: OllamaModelsPanelProps) {
  const [installed, setInstalled] = useState<LlmModel[]>([])
  const [catalog, setCatalog] = useState<OllamaCatalogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [modelInput, setModelInput] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const refresh = useCallback(async (): Promise<void> => {
    try {
      setInstalled(await getLlmProviderModels(providerId))
    } catch (error) {
      onError(error as ApiError)
    } finally {
      setLoading(false)
    }
  }, [providerId, onError])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    let cancelled = false
    void getOllamaCatalog()
      .then((entries) => {
        if (!cancelled) {
          setCatalog(entries)
        }
      })
      .catch(() => {
        // The catalog is only a convenience; free-text pull still works.
      })
    return () => {
      cancelled = true
    }
  }, [])

  const { pull, startPull } = useOllamaPull({
    providerId,
    onDone: () => {
      setModelInput('')
      void refresh()
    },
    onError,
  })

  async function handleDelete(model: string): Promise<void> {
    try {
      await deleteProviderModel(providerId, model)
      setConfirmDelete(null)
      await refresh()
    } catch (error) {
      onError(error as ApiError)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="text-xs text-[var(--muted)]">
        Models are shared across all users of this Ollama server.
      </div>

      {loading ? (
        <div className="text-xs text-[var(--muted)]">Loading models...</div>
      ) : installed.length === 0 ? (
        <div className="text-xs text-[var(--muted)]">No models installed yet.</div>
      ) : (
        <div className="flex flex-col gap-2">
          {installed.map((model) => (
            <div key={model.name} className="pixel-card">
              <div className="flex-1 text-sm">{model.name}</div>
              {confirmDelete === model.name ? (
                <>
                  <button
                    type="button"
                    className="pixel-icon danger"
                    title="Confirm delete"
                    onClick={() => void handleDelete(model.name)}
                  >
                    ✓
                  </button>
                  <button
                    type="button"
                    className="pixel-icon"
                    title="Cancel"
                    onClick={() => setConfirmDelete(null)}
                  >
                    ✕
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="pixel-icon danger"
                  onClick={() => setConfirmDelete(model.name)}
                >
                  Del
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <label className="pixel-label">
        Pull a model
        <OllamaModelPicker
          catalog={catalog}
          installed={installed}
          value={modelInput}
          onChange={setModelInput}
        />
      </label>
      <button
        type="button"
        className="pixel-button small"
        disabled={pull !== null || !modelInput.trim()}
        onClick={() => void startPull(modelInput)}
      >
        {pull !== null ? 'Pulling...' : 'Pull'}
      </button>

      {pull !== null ? (
        <div className="flex flex-col gap-1">
          <div className="flex justify-between text-xs text-[var(--muted)]">
            <span>
              {pull.model} — {pull.status}
            </span>
            {pull.percent !== null ? <span>{pull.percent}%</span> : null}
          </div>
          <div className="pixel-progress">
            <div
              className={`pixel-progress-fill${pull.percent === null ? ' indeterminate' : ''}`}
              style={pull.percent !== null ? { width: `${pull.percent}%` } : undefined}
            />
          </div>
        </div>
      ) : null}
    </div>
  )
}
