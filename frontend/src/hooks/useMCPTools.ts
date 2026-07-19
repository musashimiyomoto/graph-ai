import { useQuery } from '@tanstack/react-query'

import { getMCPTools } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'

export function useMCPTools(serverId: number | null, enabled: boolean) {
  const query = useQuery({
    queryKey: queryKeys.mcpTools(serverId ?? 0),
    queryFn: () => getMCPTools(serverId ?? 0),
    enabled: enabled && serverId !== null,
    retry: false,
  })

  return {
    tools: query.data ?? [],
    loading: query.isLoading,
    error: query.error,
  }
}
