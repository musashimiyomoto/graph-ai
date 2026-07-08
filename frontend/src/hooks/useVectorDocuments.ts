import { useCallback, useEffect, useState } from 'react'

import {
  deleteVectorDocument,
  getVectorDocuments,
  uploadVectorDocument,
} from '../lib/api'
import type { ApiError, VectorDocument, VectorUploadResult } from '../lib/types'

interface UseVectorDocumentsParams {
  collection: string
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseVectorDocumentsResult {
  documents: VectorDocument[]
  loading: boolean
  uploading: boolean
  refreshDocuments: () => Promise<void>
  removeDocument: (source: string) => Promise<boolean>
  uploadDocument: (
    file: File,
    source?: string,
  ) => Promise<VectorUploadResult | null>
}

export function useVectorDocuments({
  collection,
  enabled = true,
  onError,
}: UseVectorDocumentsParams): UseVectorDocumentsResult {
  const [documents, setDocuments] = useState<VectorDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)

  const reportError = useCallback(
    (error: ApiError): void => {
      if (onError) {
        onError(error)
      }
    },
    [onError],
  )

  const refreshDocuments = useCallback(async (): Promise<void> => {
    if (!enabled) {
      setDocuments([])
      return
    }

    setLoading(true)
    try {
      const items = await getVectorDocuments(collection)
      setDocuments(items)
    } catch (error) {
      reportError(error as ApiError)
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }, [collection, enabled, reportError])

  useEffect(() => {
    void refreshDocuments()
  }, [refreshDocuments])

  const removeDocument = useCallback(
    async (source: string): Promise<boolean> => {
      try {
        await deleteVectorDocument(collection, source)
        setDocuments((previous) => previous.filter((item) => item.source !== source))
        return true
      } catch (error) {
        reportError(error as ApiError)
        return false
      }
    },
    [collection, reportError],
  )

  const uploadDocument = useCallback(
    async (file: File, source?: string): Promise<VectorUploadResult | null> => {
      setUploading(true)
      try {
        const result = await uploadVectorDocument(collection, file, source)
        await refreshDocuments()
        return result
      } catch (error) {
        reportError(error as ApiError)
        return null
      } finally {
        setUploading(false)
      }
    },
    [collection, refreshDocuments, reportError],
  )

  return {
    documents,
    loading,
    uploading,
    refreshDocuments,
    removeDocument,
    uploadDocument,
  }
}
