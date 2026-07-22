import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { useChannelCatalog } from './useChannelCatalog'
import {
  approveExecution,
  getExecutions,
  rejectExecution,
} from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError, Execution, ExecutionSource } from '../lib/types'

interface UseActivityLogParams {
  token: string | null
  activeWorkflowId: number | null
  handleError: (error: ApiError) => void
}

interface UseActivityLogResult {
  executions: Execution[]
  loading: boolean
  decidingExecutionId: number | null
  sourceLabels: Record<string, string>
  handleApprove: (executionId: number) => Promise<void>
  handleReject: (executionId: number) => Promise<void>
  refresh: () => Promise<void>
}

export function useActivityLog({
  token,
  activeWorkflowId,
  handleError,
}: UseActivityLogParams): UseActivityLogResult {
  const active = token !== null && activeWorkflowId !== null
  const resolvedWorkflowId = activeWorkflowId ?? 0
  const [decidingExecutionId, setDecidingExecutionId] = useState<number | null>(null)
  const { channelCatalog, loading: catalogLoading, sourceLabels } = useChannelCatalog({
    handleError,
  })
  const activitySources = useMemo<ExecutionSource[]>(
    () => channelCatalog.filter((channel) => channel.activity).map((channel) => channel.source),
    [channelCatalog],
  )

  const query = useQuery({
    queryKey: queryKeys.activityLog(resolvedWorkflowId, activitySources),
    queryFn: () => getExecutions(resolvedWorkflowId, activitySources),
    enabled: active && activitySources.length > 0,
    refetchInterval: active && activitySources.length > 0 ? 3000 : false,
  })

  useEffect(() => {
    if (query.error) {
      handleError(query.error)
    }
  }, [query.error, handleError])

  const decideApproval = useCallback(
    async (executionId: number, approved: boolean): Promise<void> => {
      setDecidingExecutionId(executionId)
      try {
        if (approved) {
          await approveExecution(executionId)
        } else {
          await rejectExecution(executionId)
        }
        await query.refetch()
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setDecidingExecutionId(null)
      }
    },
    [handleError, query],
  )

  return {
    executions: active ? (query.data ?? []) : [],
    loading: active && (catalogLoading || query.isLoading),
    decidingExecutionId,
    sourceLabels,
    handleApprove: async (executionId: number) => {
      await decideApproval(executionId, true)
    },
    handleReject: async (executionId: number) => {
      await decideApproval(executionId, false)
    },
    refresh: async () => {
      await query.refetch()
    },
  }
}
