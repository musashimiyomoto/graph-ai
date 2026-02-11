import { useEffect, useState } from 'react'

import { getLlmProviderModels } from '../lib/api'
import type { ApiError, LlmModel } from '../lib/types'

interface UseProviderModelsParams {
  providerId: number | null
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseProviderModelsResult {
  models: LlmModel[]
}

export function useProviderModels({
  providerId,
  enabled = true,
  onError,
}: UseProviderModelsParams): UseProviderModelsResult {
  const [models, setModels] = useState<LlmModel[]>([])
  const [loadedProviderId, setLoadedProviderId] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false

    if (!enabled || !providerId) {
      return () => {
        cancelled = true
      }
    }

    void getLlmProviderModels(providerId)
      .then((items) => {
        if (!cancelled) {
          setModels(items)
          setLoadedProviderId(providerId)
        }
      })
      .catch((error: ApiError) => {
        if (!cancelled) {
          if (onError) {
            onError(error)
          }
          setModels([])
          setLoadedProviderId(providerId)
        }
      })

    return () => {
      cancelled = true
    }
  }, [enabled, onError, providerId])

  return {
    models:
      enabled && providerId !== null && loadedProviderId === providerId ? models : [],
  }
}
