import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo } from 'react'

import { getNodeCatalog } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError, NodeCatalogItem } from '../lib/types'

interface UseNodeCatalogParams {
  handleError: (error: ApiError) => void
}

interface UseNodeCatalogResult {
  nodeCatalog: NodeCatalogItem[]
  nodeCatalogByType: Record<string, NodeCatalogItem>
}

export function useNodeCatalog({
  handleError,
}: UseNodeCatalogParams): UseNodeCatalogResult {
  const { data, error } = useQuery({
    queryKey: queryKeys.nodeCatalog(),
    queryFn: getNodeCatalog,
  })

  useEffect(() => {
    if (error) {
      handleError(error)
    }
  }, [error, handleError])

  const nodeCatalog = useMemo(() => data ?? [], [data])

  const nodeCatalogByType = useMemo(
    () =>
      Object.fromEntries(
        nodeCatalog.map((item) => [item.type, item]),
      ) as Record<string, NodeCatalogItem>,
    [nodeCatalog],
  )

  return {
    nodeCatalog,
    nodeCatalogByType,
  }
}
