import { useCallback, useEffect, useState } from 'react'

import { getExecutions } from '../lib/api'
import type { ApiError, Execution } from '../lib/types'

interface UseActivityLogParams {
  token: string | null
  activeWorkflowId: number | null
  handleError: (error: ApiError) => void
}

interface UseActivityLogResult {
  executions: Execution[]
  loading: boolean
  refresh: () => Promise<void>
}

// Read-only log of real inbound traffic (currently only Telegram), kept
// separate from useExecutions' manual test runs so a workflow's actual
// usage never gets mixed into the owner's test sandbox.
export function useActivityLog({
  token,
  activeWorkflowId,
  handleError,
}: UseActivityLogParams): UseActivityLogResult {
  const [executions, setExecutions] = useState<Execution[]>([])
  const [loading, setLoading] = useState<boolean>(false)

  const refresh = useCallback(async (): Promise<void> => {
    if (!token || !activeWorkflowId) {
      setExecutions([])
      return
    }
    setLoading(true)
    try {
      const items = await getExecutions(activeWorkflowId, 'telegram')
      setExecutions(items)
    } catch (error) {
      handleError(error as ApiError)
    } finally {
      setLoading(false)
    }
  }, [activeWorkflowId, handleError, token])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return { executions, loading, refresh }
}
