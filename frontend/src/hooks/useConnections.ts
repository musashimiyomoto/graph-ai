import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  checkConnectionHealth,
  createConnection,
  deleteConnection,
  getConnections,
  refreshConnection,
  revokeConnection,
  startConnectionOAuth,
} from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type {
  ApiError,
  Connection,
  ConnectionCreatePayload,
  ConnectionOAuthStartResponse,
} from '../lib/types'

interface UseConnectionsParams {
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface OAuthStartInput {
  connectionId: number
  redirectUri: string
}

export function useConnections({
  enabled = true,
  onError,
}: UseConnectionsParams = {}) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: queryKeys.connections(),
    queryFn: getConnections,
    enabled,
  })

  function replaceConnection(updated: Connection): void {
    queryClient.setQueryData(
      queryKeys.connections(),
      (previous: Connection[] | undefined) =>
        previous?.map((item) => (item.id === updated.id ? updated : item)) ?? [updated],
    )
  }

  const createMutation = useMutation({
    mutationFn: createConnection,
    onSuccess: (created) => {
      queryClient.setQueryData(
        queryKeys.connections(),
        (previous: Connection[] | undefined) => [...(previous ?? []), created],
      )
    },
  })
  const oauthMutation = useMutation({
    mutationFn: ({ connectionId, redirectUri }: OAuthStartInput) =>
      startConnectionOAuth(connectionId, redirectUri),
  })
  const refreshMutation = useMutation({
    mutationFn: refreshConnection,
    onSuccess: replaceConnection,
  })
  const healthMutation = useMutation({
    mutationFn: checkConnectionHealth,
    onSuccess: replaceConnection,
  })
  const revokeMutation = useMutation({
    mutationFn: revokeConnection,
    onSuccess: replaceConnection,
  })
  const deleteMutation = useMutation({
    mutationFn: deleteConnection,
    onSuccess: (_data, connectionId) => {
      queryClient.setQueryData(
        queryKeys.connections(),
        (previous: Connection[] | undefined) =>
          previous?.filter((item) => item.id !== connectionId) ?? [],
      )
    },
  })

  useEffect(() => {
    if (query.error) {
      onError?.(query.error)
    }
  }, [query.error, onError])

  async function runMutation<T>(operation: () => Promise<T>): Promise<T | null> {
    try {
      return await operation()
    } catch (error) {
      onError?.(error as ApiError)
      return null
    }
  }

  async function addConnection(
    payload: ConnectionCreatePayload,
  ): Promise<Connection | null> {
    return runMutation(() => createMutation.mutateAsync(payload))
  }

  async function beginOAuth(
    connectionId: number,
    redirectUri: string,
  ): Promise<ConnectionOAuthStartResponse | null> {
    return runMutation(() =>
      oauthMutation.mutateAsync({ connectionId, redirectUri }),
    )
  }

  async function refreshOAuth(connectionId: number): Promise<boolean> {
    return (await runMutation(() => refreshMutation.mutateAsync(connectionId))) !== null
  }

  async function checkHealth(connectionId: number): Promise<boolean> {
    return (await runMutation(() => healthMutation.mutateAsync(connectionId))) !== null
  }

  async function revoke(connectionId: number): Promise<boolean> {
    return (await runMutation(() => revokeMutation.mutateAsync(connectionId))) !== null
  }

  async function removeConnection(connectionId: number): Promise<boolean> {
    return (await runMutation(() => deleteMutation.mutateAsync(connectionId))) !== null
  }

  return {
    connections: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
    creating: createMutation.isPending,
    operating:
      oauthMutation.isPending ||
      refreshMutation.isPending ||
      healthMutation.isPending ||
      revokeMutation.isPending ||
      deleteMutation.isPending,
    addConnection,
    beginOAuth,
    refreshOAuth,
    checkHealth,
    revoke,
    removeConnection,
    reload: query.refetch,
  }
}
