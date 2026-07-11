import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  createLlmProvider,
  deleteLlmProvider,
  getLlmProviders,
} from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type {
  ApiError,
  LlmProvider,
  LlmProviderCreatePayload,
} from '../lib/types'

interface UseLlmProvidersParams {
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseLlmProvidersResult {
  providers: LlmProvider[]
  loading: boolean
  creating: boolean
  refreshProviders: () => Promise<void>
  createProvider: (
    payload: LlmProviderCreatePayload,
  ) => Promise<LlmProvider | null>
  removeProvider: (providerId: number) => Promise<boolean>
}

// Shares one cached list across every consumer (Settings' provider list and
// NodeFieldsForm's provider picker both read/invalidate the same query key),
// so creating/deleting a provider in one place is immediately reflected in
// the other instead of each hook instance holding its own stale copy.
export function useLlmProviders({
  enabled = true,
  onError,
}: UseLlmProvidersParams): UseLlmProvidersResult {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: queryKeys.llmProviders(),
    queryFn: getLlmProviders,
    enabled,
  })

  const createMutation = useMutation({
    mutationFn: createLlmProvider,
    onSuccess: (created) => {
      queryClient.setQueryData(
        queryKeys.llmProviders(),
        (previous: LlmProvider[] | undefined) => [...(previous ?? []), created],
      )
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteLlmProvider,
    onSuccess: (_data, providerId) => {
      queryClient.setQueryData(
        queryKeys.llmProviders(),
        (previous: LlmProvider[] | undefined) =>
          previous?.filter((item) => item.id !== providerId) ?? [],
      )
    },
  })

  async function createProvider(
    payload: LlmProviderCreatePayload,
  ): Promise<LlmProvider | null> {
    try {
      return await createMutation.mutateAsync(payload)
    } catch (error) {
      onError?.(error as ApiError)
      return null
    }
  }

  async function removeProvider(providerId: number): Promise<boolean> {
    try {
      await deleteMutation.mutateAsync(providerId)
      return true
    } catch (error) {
      onError?.(error as ApiError)
      return false
    }
  }

  useEffect(() => {
    if (query.error) {
      onError?.(query.error)
    }
  }, [query.error, onError])

  return {
    providers: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
    creating: createMutation.isPending,
    refreshProviders: async () => {
      await query.refetch()
    },
    createProvider,
    removeProvider,
  }
}
