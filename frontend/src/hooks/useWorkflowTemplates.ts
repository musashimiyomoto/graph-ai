import { useQuery } from '@tanstack/react-query'

import { getWorkflowTemplates } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { WorkflowTemplate } from '../lib/types'

interface UseWorkflowTemplatesParams {
  enabled?: boolean
}

interface UseWorkflowTemplatesResult {
  templates: WorkflowTemplate[]
  loading: boolean
}

export function useWorkflowTemplates({
  enabled = true,
}: UseWorkflowTemplatesParams = {}): UseWorkflowTemplatesResult {
  const query = useQuery({
    queryKey: queryKeys.workflowTemplates(),
    queryFn: getWorkflowTemplates,
    enabled,
  })

  return {
    templates: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
  }
}
