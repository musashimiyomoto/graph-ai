import { useCallback, useEffect, useState } from 'react'

import {
  deleteVectorCollection,
  getVectorCollections,
} from '../lib/api'
import type { ApiError, VectorCollection } from '../lib/types'

interface UseVectorCollectionsParams {
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseVectorCollectionsResult {
  collections: VectorCollection[]
  loading: boolean
  refreshCollections: () => Promise<void>
  removeCollection: (name: string) => Promise<boolean>
}

export function useVectorCollections({
  enabled = true,
  onError,
}: UseVectorCollectionsParams): UseVectorCollectionsResult {
  const [collections, setCollections] = useState<VectorCollection[]>([])
  const [loading, setLoading] = useState(false)

  const reportError = useCallback(
    (error: ApiError): void => {
      if (onError) {
        onError(error)
      }
    },
    [onError],
  )

  const refreshCollections = useCallback(async (): Promise<void> => {
    if (!enabled) {
      setCollections([])
      return
    }

    setLoading(true)
    try {
      const items = await getVectorCollections()
      setCollections(items)
    } catch (error) {
      reportError(error as ApiError)
      setCollections([])
    } finally {
      setLoading(false)
    }
  }, [enabled, reportError])

  useEffect(() => {
    void refreshCollections()
  }, [refreshCollections])

  const removeCollection = useCallback(
    async (name: string): Promise<boolean> => {
      try {
        await deleteVectorCollection(name)
        setCollections((previous) => previous.filter((item) => item.name !== name))
        return true
      } catch (error) {
        reportError(error as ApiError)
        return false
      }
    },
    [reportError],
  )

  return {
    collections,
    loading,
    refreshCollections,
    removeCollection,
  }
}
