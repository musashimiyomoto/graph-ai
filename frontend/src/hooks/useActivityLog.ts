import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { getExecutions } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError, Execution } from '../lib/types'

interface UseActivityLogParams {
  token: string | null
  activeWorkflowId: number | null
  handleError: (error: ApiError) => void
}

interface UseActivityLogResult {
  executions: Execution[]
  loading: boolean
  refresh: () => Promise<void>
}

// Read-only log of real inbound traffic (currently only Telegram), kept
// separate from useExecutions' manual test runs so a workflow's actual
// usage never gets mixed into the owner's test sandbox.
export function useActivityLog({
  token,
  activeWorkflowId,
  handleError,
}: UseActivityLogParams): UseActivityLogResult {
  const active = token !== null && activeWorkflowId !== null
  const resolvedWorkflowId = activeWorkflowId ?? 0

  const query = useQuery({
    queryKey: queryKeys.activityLog(resolvedWorkflowId),
    queryFn: () => getExecutions(resolvedWorkflowId, 'telegram'),
    enabled: active,
  })

  useEffect(() => {
    if (query.error) {
      handleError(query.error)
    }
  }, [query.error, handleError])

  return {
    executions: active ? (query.data ?? []) : [],
    loading: active && query.isLoading,
    refresh: async () => {
      await query.refetch()
    },
  }
}
