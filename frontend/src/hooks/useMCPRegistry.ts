import { useQuery } from '@tanstack/react-query'

import { searchMCPRegistry } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'

export function useMCPRegistry(search: string, enabled: boolean) {
  const query = useQuery({
    queryKey: queryKeys.mcpRegistry(search),
    queryFn: () => searchMCPRegistry(search),
    enabled,
    staleTime: 60 * 60 * 1000,
    retry: false,
  })

  return {
    servers: query.data ?? [],
    loading: query.isLoading,
    error: query.error,
  }
}
