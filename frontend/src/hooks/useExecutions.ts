import { useCallback, useEffect, useState } from 'react'

import { createExecution, getExecutions } from '../lib/api'
import type { ApiError, Execution } from '../lib/types'

interface UseExecutionsParams {
  token: string | null
  activeWorkflowId: number | null
  setLoading: (value: boolean) => void
  setError: (value: string | null) => void
  handleError: (error: ApiError) => void
}

interface UseExecutionsResult {
  executions: Execution[]
  executionsLoading: boolean
  lastExecution: Execution | null
  runInput: string
  clearExecutions: () => void
  handleRun: (input: string) => Promise<void>
  refreshExecutions: (workflowId: number) => Promise<void>
}

export function useExecutions({
  token,
  activeWorkflowId,
  setLoading,
  setError,
  handleError,
}: UseExecutionsParams): UseExecutionsResult {
  const [runInput, setRunInput] = useState<string>('{}')
  const [executions, setExecutions] = useState<Execution[]>([])
  const [executionsLoading, setExecutionsLoading] = useState<boolean>(false)
  const [lastExecution, setLastExecution] = useState<Execution | null>(null)

  const refreshExecutions = useCallback(
    async (workflowId: number): Promise<void> => {
      setExecutionsLoading(true)
      try {
        const items = await getExecutions(workflowId)
        setExecutions(items)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setExecutionsLoading(false)
      }
    },
    [handleError],
  )

  useEffect(() => {
    if (!token || !activeWorkflowId) {
      setExecutions([])
      setLastExecution(null)
      return
    }

    void refreshExecutions(activeWorkflowId)
  }, [activeWorkflowId, refreshExecutions, token])

  const handleRun = useCallback(
    async (input: string): Promise<void> => {
      if (!activeWorkflowId) {
        return
      }
      setRunInput(input)
      setLoading(true)
      try {
        const parsed = input.trim() ? (JSON.parse(input) as object) : null
        const execution = await createExecution(activeWorkflowId, parsed)
        setLastExecution(execution)
        await refreshExecutions(activeWorkflowId)
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [activeWorkflowId, handleError, refreshExecutions, setError, setLoading],
  )

  const clearExecutions = useCallback(() => {
    setExecutions([])
    setLastExecution(null)
  }, [])

  return {
    executions,
    executionsLoading,
    lastExecution,
    runInput,
    clearExecutions,
    handleRun,
    refreshExecutions,
  }
}
