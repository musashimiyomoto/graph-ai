import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { deleteVectorDocument, getVectorDocuments } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError, VectorDocument } from '../lib/types'

interface UseVectorDocumentsParams {
  collection: string
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseVectorDocumentsResult {
  documents: VectorDocument[]
  loading: boolean
  refreshDocuments: () => Promise<void>
  removeDocument: (source: string) => Promise<boolean>
}

export function useVectorDocuments({
  collection,
  enabled = true,
  onError,
}: UseVectorDocumentsParams): UseVectorDocumentsResult {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: queryKeys.vectorDocuments(collection),
    queryFn: () => getVectorDocuments(collection),
    enabled,
  })

  const deleteMutation = useMutation({
    mutationFn: (source: string) => deleteVectorDocument(collection, source),
    onSuccess: (_data, source) => {
      queryClient.setQueryData(
        queryKeys.vectorDocuments(collection),
        (previous: VectorDocument[] | undefined) =>
          previous?.filter((item) => item.source !== source) ?? [],
      )
    },
  })

  async function removeDocument(source: string): Promise<boolean> {
    try {
      await deleteMutation.mutateAsync(source)
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
    documents: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
    refreshDocuments: async () => {
      await query.refetch()
    },
    removeDocument,
  }
}
