import { useQuery } from '@tanstack/react-query'

import { getWorkflows } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'

export function useWorkflowOptions(enabled: boolean) {
  const query = useQuery({
    queryKey: queryKeys.workflows(),
    queryFn: getWorkflows,
    enabled,
  })

  return {
    workflows: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
  }
}
