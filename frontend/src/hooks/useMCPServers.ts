import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  createMCPServer,
  deleteMCPServer,
  getMCPServers,
} from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type {
  ApiError,
  MCPServer,
  MCPServerCreatePayload,
} from '../lib/types'

interface UseMCPServersParams {
  enabled?: boolean
  onError?: (error: ApiError) => void
}

export function useMCPServers({
  enabled = true,
  onError,
}: UseMCPServersParams = {}) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: queryKeys.mcpServers(),
    queryFn: getMCPServers,
    enabled,
  })
  const createMutation = useMutation({
    mutationFn: createMCPServer,
    onSuccess: (created) => {
      queryClient.setQueryData(
        queryKeys.mcpServers(),
        (previous: MCPServer[] | undefined) => [...(previous ?? []), created],
      )
    },
  })
  const deleteMutation = useMutation({
    mutationFn: deleteMCPServer,
    onSuccess: (_data, serverId) => {
      queryClient.setQueryData(
        queryKeys.mcpServers(),
        (previous: MCPServer[] | undefined) =>
          previous?.filter((server) => server.id !== serverId) ?? [],
      )
      queryClient.removeQueries({ queryKey: queryKeys.mcpTools(serverId) })
    },
  })

  useEffect(() => {
    if (query.error) {
      onError?.(query.error)
    }
  }, [query.error, onError])

  async function createServer(
    payload: MCPServerCreatePayload,
  ): Promise<MCPServer | null> {
    try {
      return await createMutation.mutateAsync(payload)
    } catch (error) {
      onError?.(error as ApiError)
      return null
    }
  }

  async function removeServer(serverId: number): Promise<boolean> {
    try {
      await deleteMutation.mutateAsync(serverId)
      return true
    } catch (error) {
      onError?.(error as ApiError)
      return false
    }
  }

  return {
    servers: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
    creating: createMutation.isPending,
    createServer,
    removeServer,
  }
}
