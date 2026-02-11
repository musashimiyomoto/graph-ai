import { useCallback, useEffect, useState } from 'react'

import { createExecution, getExecutions } from '../lib/api'
import type { ApiError, Execution, RunInputPayload } from '../lib/types'

const POLL_INTERVAL_MS = 5000

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
  runInput: RunInputPayload
  clearExecutions: () => void
  handleRun: (input: RunInputPayload) => Promise<void>
  refreshExecutions: (workflowId: number) => Promise<void>
}

export function useExecutions({
  token,
  activeWorkflowId,
  setLoading,
  setError,
  handleError,
}: UseExecutionsParams): UseExecutionsResult {
  const [runInput, setRunInput] = useState<RunInputPayload>({ value: '' })
  const [executions, setExecutions] = useState<Execution[]>([])
  const [executionsLoading, setExecutionsLoading] = useState<boolean>(false)
  const [lastExecution, setLastExecution] = useState<Execution | null>(null)

  const refreshExecutions = useCallback(
    async (workflowId: number): Promise<void> => {
      setExecutionsLoading(true)
      try {
        const items = await getExecutions(workflowId)
        setExecutions(items)
        const latest = [...items].sort((first, second) => second.id - first.id)[0] ?? null
        setLastExecution(latest)
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

  useEffect(() => {
    if (!token || !activeWorkflowId) {
      return
    }
    if (!executions.some((execution) => execution.status === 'running')) {
      return
    }

    const timer = window.setInterval(() => {
      void refreshExecutions(activeWorkflowId)
    }, POLL_INTERVAL_MS)

    return () => window.clearInterval(timer)
  }, [activeWorkflowId, executions, refreshExecutions, token])

  const handleRun = useCallback(
    async (input: RunInputPayload): Promise<void> => {
      if (!activeWorkflowId) {
        return
      }
      setRunInput(input)
      setLoading(true)
      try {
        const execution = await createExecution(activeWorkflowId, input)
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
