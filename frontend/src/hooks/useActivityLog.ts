import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'

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
  handleApprove: (executionId: number) => Promise<void>
  handleReject: (executionId: number) => Promise<void>
  refresh: () => Promise<void>
}

// Real inbound traffic (channel messages and scheduled runs), kept separate
// from useExecutions' manual test runs. Approval decisions remain actionable
// here because these executions belong to real production-facing channels.
const ACTIVITY_LOG_SOURCES: ExecutionSource[] = [
  'telegram',
  'schedule',
  'email',
  'webhook',
  'web_chat',
]

export function useActivityLog({
  token,
  activeWorkflowId,
  handleError,
}: UseActivityLogParams): UseActivityLogResult {
  const active = token !== null && activeWorkflowId !== null
  const resolvedWorkflowId = activeWorkflowId ?? 0
  const [decidingExecutionId, setDecidingExecutionId] = useState<number | null>(null)

  const query = useQuery({
    queryKey: queryKeys.activityLog(resolvedWorkflowId),
    queryFn: () => getExecutions(resolvedWorkflowId, ACTIVITY_LOG_SOURCES),
    enabled: active,
    refetchInterval: active ? 3000 : false,
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
    loading: active && query.isLoading,
    decidingExecutionId,
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
