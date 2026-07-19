import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { getWorkflows } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'

export function useWorkflowOptions(enabled: boolean, excludedWorkflowId: number | null) {
  const query = useQuery({
    queryKey: queryKeys.workflows(),
    queryFn: getWorkflows,
    enabled,
  })
  const workflows = useMemo(
    () =>
      (query.data ?? []).filter((workflow) => workflow.id !== excludedWorkflowId),
    [excludedWorkflowId, query.data],
  )

  return {
    workflows: enabled ? workflows : [],
    loading: enabled && query.isLoading,
  }
}
