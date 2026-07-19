import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  approveExecution,
  cancelExecution,
  createExecution,
  getExecutions,
  rejectExecution,
  streamExecution,
} from '../lib/api'
import type { ApiError, Execution, ExecutionSource, RunInputPayload } from '../lib/types'
import { ACTIVE_STATUSES } from '../lib/types'

// Interval for the polling fallback when the SSE stream ends before settling.
const STREAM_POLL_FALLBACK_MS = 3000
// Scoped to the owner's own test runs — real inbound traffic (Telegram,
// schedule) is shown separately in the Activity Log.
const TEST_RUN_SOURCES: ExecutionSource[] = ['manual']

interface UseExecutionsParams {
  token: string | null
  activeWorkflowId: number | null
  setLoading: (value: boolean) => void
  setError: (value: string | null) => void
  handleError: (error: ApiError) => void
}

// Live per-node token text for the execution currently streaming.
export type LiveTokens = Record<number, string>

interface UseExecutionsResult {
  executions: Execution[]
  executionsLoading: boolean
  cancelling: boolean
  decidingExecutionId: number | null
  lastExecution: Execution | null
  liveTokens: LiveTokens
  runInput: RunInputPayload
  clearExecutions: () => void
  handleRun: (input: RunInputPayload) => Promise<void>
  handleCancel: () => Promise<void>
  handleApprove: (executionId: number) => Promise<void>
  handleReject: (executionId: number) => Promise<void>
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
  const [cancelling, setCancelling] = useState<boolean>(false)
  const [decidingExecutionId, setDecidingExecutionId] = useState<number | null>(null)
  const [lastExecution, setLastExecution] = useState<Execution | null>(null)
  const [liveTokens, setLiveTokens] = useState<LiveTokens>({})

  const refreshExecutions = useCallback(
    async (workflowId: number): Promise<void> => {
      setExecutionsLoading(true)
      try {
        const items = await getExecutions(workflowId, TEST_RUN_SOURCES)
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

  const activeExecutionId = useMemo(
    () =>
      lastExecution && ACTIVE_STATUSES.includes(lastExecution.status)
        ? lastExecution.id
        : null,
    [lastExecution],
  )

  useEffect(() => {
    if (!token || !activeWorkflowId || activeExecutionId === null) {
      return
    }

    const controller = new AbortController()
    const workflowId = activeWorkflowId
    const executionId = activeExecutionId
    let stopped = false
    setLiveTokens({})

    // Fallback when the SSE stream ends before the execution settles (stream
    // unsupported/blocked, or the server capped the stream and sent `expired`).
    async function pollUntilSettled(): Promise<void> {
      while (!stopped && !controller.signal.aborted) {
        await new Promise((resolve) => setTimeout(resolve, STREAM_POLL_FALLBACK_MS))
        if (stopped || controller.signal.aborted) {
          return
        }
        try {
          const items = await getExecutions(workflowId, TEST_RUN_SOURCES)
          setExecutions(items)
          const current = items.find((item) => item.id === executionId)
          if (current) {
            setLastExecution(current)
            if (!ACTIVE_STATUSES.includes(current.status)) {
              return
            }
          }
        } catch {
          // Transient fetch failure; keep polling until aborted.
        }
      }
    }

    void streamExecution(
      executionId,
      (event) => {
        if (event.type === 'token') {
          setLiveTokens((previous) => ({
            ...previous,
            [event.node_id]: (previous[event.node_id] ?? '') + event.delta,
          }))
          return
        }
        if (event.type === 'token_reset') {
          // The node is retrying: drop its partial text from the failed
          // attempt so the retry's tokens don't append after it.
          setLiveTokens((previous) => ({ ...previous, [event.node_id]: '' }))
          return
        }
        if (event.type === 'expired') {
          return
        }

        const { execution } = event
        setLastExecution(execution)
        setExecutions((previous) =>
          previous.map((item) =>
            item.id === execution.id ? execution : item,
          ),
        )
      },
      controller.signal,
    )
      .catch(() => {
        // Stream unsupported or interrupted; the polling fallback recovers.
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          void pollUntilSettled()
        }
      })

    return () => {
      stopped = true
      controller.abort()
    }
  }, [activeExecutionId, activeWorkflowId, token])

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

  const handleCancel = useCallback(async (): Promise<void> => {
    if (!lastExecution || !ACTIVE_STATUSES.includes(lastExecution.status)) {
      return
    }

    setCancelling(true)
    try {
      const cancelled = await cancelExecution(lastExecution.id)
      setLastExecution(cancelled)
      setExecutions((previous) =>
        previous.map((item) =>
          item.id === cancelled.id ? cancelled : item,
        ),
      )
      setLiveTokens({})
      setError(null)
    } catch (error) {
      handleError(error as ApiError)
    } finally {
      setCancelling(false)
    }
  }, [handleError, lastExecution, setError])

  const decideApproval = useCallback(
    async (executionId: number, approved: boolean): Promise<void> => {
      setDecidingExecutionId(executionId)
      try {
        const execution = approved
          ? await approveExecution(executionId)
          : await rejectExecution(executionId)
        setLastExecution(execution)
        setExecutions((previous) =>
          previous.map((item) =>
            item.id === execution.id ? execution : item,
          ),
        )
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setDecidingExecutionId(null)
      }
    },
    [handleError, setError],
  )

  const handleApprove = useCallback(
    async (executionId: number): Promise<void> => {
      await decideApproval(executionId, true)
    },
    [decideApproval],
  )

  const handleReject = useCallback(
    async (executionId: number): Promise<void> => {
      await decideApproval(executionId, false)
    },
    [decideApproval],
  )

  const clearExecutions = useCallback(() => {
    setExecutions([])
    setLastExecution(null)
  }, [])

  return {
    executions,
    executionsLoading,
    cancelling,
    decidingExecutionId,
    lastExecution,
    liveTokens,
    runInput,
    clearExecutions,
    handleRun,
    handleCancel,
    handleApprove,
    handleReject,
    refreshExecutions,
  }
}
