import { useEffect, useMemo, useState } from 'react'

import { getNodeCatalog } from '../lib/api'
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
  const [nodeCatalog, setNodeCatalog] = useState<NodeCatalogItem[]>([])

  useEffect(() => {
    let cancelled = false

    void getNodeCatalog()
      .then((catalog) => {
        if (!cancelled) {
          setNodeCatalog(catalog)
        }
      })
      .catch((error: ApiError) => {
        if (!cancelled) {
          handleError(error)
          setNodeCatalog([])
        }
      })

    return () => {
      cancelled = true
    }
  }, [handleError])

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
