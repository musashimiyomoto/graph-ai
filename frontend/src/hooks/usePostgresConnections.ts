import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  createPostgresConnection,
  deletePostgresConnection,
  getPostgresConnections,
} from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type {
  ApiError,
  PostgresConnection,
  PostgresConnectionCreatePayload,
} from '../lib/types'

interface UsePostgresConnectionsParams {
  enabled?: boolean
  onError?: (error: ApiError) => void
}

export function usePostgresConnections({
  enabled = true,
  onError,
}: UsePostgresConnectionsParams = {}) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: queryKeys.postgresConnections(),
    queryFn: getPostgresConnections,
    enabled,
  })
  const createMutation = useMutation({
    mutationFn: createPostgresConnection,
    onSuccess: (created) => {
      queryClient.setQueryData(
        queryKeys.postgresConnections(),
        (previous: PostgresConnection[] | undefined) => [...(previous ?? []), created],
      )
    },
  })
  const deleteMutation = useMutation({
    mutationFn: deletePostgresConnection,
    onSuccess: (_data, connectionId) => {
      queryClient.setQueryData(
        queryKeys.postgresConnections(),
        (previous: PostgresConnection[] | undefined) =>
          previous?.filter((item) => item.id !== connectionId) ?? [],
      )
    },
  })

  useEffect(() => {
    if (query.error) {
      onError?.(query.error)
    }
  }, [query.error, onError])

  async function createConnection(
    payload: PostgresConnectionCreatePayload,
  ): Promise<PostgresConnection | null> {
    try {
      return await createMutation.mutateAsync(payload)
    } catch (error) {
      onError?.(error as ApiError)
      return null
    }
  }

  async function removeConnection(connectionId: number): Promise<boolean> {
    try {
      await deleteMutation.mutateAsync(connectionId)
      return true
    } catch (error) {
      onError?.(error as ApiError)
      return false
    }
  }

  return {
    connections: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
    creating: createMutation.isPending,
    createConnection,
    removeConnection,
  }
}
