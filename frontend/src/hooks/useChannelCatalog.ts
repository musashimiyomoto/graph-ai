import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo } from 'react'

import { getChannelCatalog } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError, ChannelCatalogItem } from '../lib/types'

interface UseChannelCatalogParams {
  handleError: (error: ApiError) => void
}

interface UseChannelCatalogResult {
  channelCatalog: ChannelCatalogItem[]
  loading: boolean
  sourceLabels: Record<string, string>
}

export function useChannelCatalog({
  handleError,
}: UseChannelCatalogParams): UseChannelCatalogResult {
  const query = useQuery({
    queryKey: queryKeys.channelCatalog(),
    queryFn: getChannelCatalog,
  })

  useEffect(() => {
    if (query.error) {
      handleError(query.error)
    }
  }, [query.error, handleError])

  const channelCatalog = useMemo(() => query.data ?? [], [query.data])
  const sourceLabels = useMemo(
    () => Object.fromEntries(channelCatalog.map((channel) => [channel.source, channel.label])),
    [channelCatalog],
  )

  return {
    channelCatalog,
    loading: query.isLoading,
    sourceLabels,
  }
}
