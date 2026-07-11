import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { deleteVectorCollection, getVectorCollections } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError, VectorCollection } from '../lib/types'

interface UseVectorCollectionsParams {
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseVectorCollectionsResult {
  collections: VectorCollection[]
  loading: boolean
  refreshCollections: () => Promise<void>
  removeCollection: (name: string) => Promise<boolean>
}

export function useVectorCollections({
  enabled = true,
  onError,
}: UseVectorCollectionsParams): UseVectorCollectionsResult {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: queryKeys.vectorCollections(),
    queryFn: getVectorCollections,
    enabled,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteVectorCollection,
    onSuccess: (_data, name) => {
      queryClient.setQueryData(
        queryKeys.vectorCollections(),
        (previous: VectorCollection[] | undefined) =>
          previous?.filter((item) => item.name !== name) ?? [],
      )
    },
  })

  async function removeCollection(name: string): Promise<boolean> {
    try {
      await deleteMutation.mutateAsync(name)
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
    collections: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
    refreshCollections: async () => {
      await query.refetch()
    },
    removeCollection,
  }
}
