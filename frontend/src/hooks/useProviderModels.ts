import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { getLlmProviderModels } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError, LlmModel } from '../lib/types'

interface UseProviderModelsParams {
  providerId: number | null
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseProviderModelsResult {
  models: LlmModel[]
  loading: boolean
}

export function useProviderModels({
  providerId,
  enabled = true,
  onError,
}: UseProviderModelsParams): UseProviderModelsResult {
  const active = enabled && providerId !== null
  const resolvedProviderId = providerId ?? 0

  const query = useQuery({
    queryKey: queryKeys.llmProviderModels(resolvedProviderId),
    queryFn: () => getLlmProviderModels(resolvedProviderId),
    enabled: active,
  })

  useEffect(() => {
    if (query.error) {
      onError?.(query.error)
    }
  }, [query.error, onError])

  return {
    models: active ? (query.data ?? []) : [],
    loading: active && query.isLoading,
  }
}
