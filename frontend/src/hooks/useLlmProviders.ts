import { useCallback, useEffect, useState } from 'react'

import {
  createLlmProvider,
  deleteLlmProvider,
  getLlmProviders,
} from '../lib/api'
import type {
  ApiError,
  LlmProvider,
  LlmProviderCreatePayload,
} from '../lib/types'

interface UseLlmProvidersParams {
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseLlmProvidersResult {
  providers: LlmProvider[]
  loading: boolean
  creating: boolean
  refreshProviders: () => Promise<void>
  createProvider: (
    payload: LlmProviderCreatePayload,
  ) => Promise<LlmProvider | null>
  removeProvider: (providerId: number) => Promise<boolean>
}

export function useLlmProviders({
  enabled = true,
  onError,
}: UseLlmProvidersParams): UseLlmProvidersResult {
  const [providers, setProviders] = useState<LlmProvider[]>([])
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)

  const reportError = useCallback(
    (error: ApiError): void => {
      if (onError) {
        onError(error)
      }
    },
    [onError],
  )

  const refreshProviders = useCallback(async (): Promise<void> => {
    if (!enabled) {
      setProviders([])
      return
    }

    setLoading(true)
    try {
      const items = await getLlmProviders()
      setProviders(items)
    } catch (error) {
      reportError(error as ApiError)
      setProviders([])
    } finally {
      setLoading(false)
    }
  }, [enabled, reportError])

  useEffect(() => {
    void refreshProviders()
  }, [refreshProviders])

  const createProvider = useCallback(
    async (payload: LlmProviderCreatePayload): Promise<LlmProvider | null> => {
      setCreating(true)
      try {
        const created = await createLlmProvider(payload)
        setProviders((previous) => [...previous, created])
        return created
      } catch (error) {
        reportError(error as ApiError)
        return null
      } finally {
        setCreating(false)
      }
    },
    [reportError],
  )

  const removeProvider = useCallback(
    async (providerId: number): Promise<boolean> => {
      try {
        await deleteLlmProvider(providerId)
        setProviders((previous) => previous.filter((item) => item.id !== providerId))
        return true
      } catch (error) {
        reportError(error as ApiError)
        return false
      }
    },
    [reportError],
  )

  return {
    providers,
    loading,
    creating,
    refreshProviders,
    createProvider,
    removeProvider,
  }
}
