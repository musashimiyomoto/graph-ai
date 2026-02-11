import { useCallback, useEffect, useState } from 'react'

import {
  createWorkflow,
  deleteWorkflow,
  getWorkflows,
  updateWorkflow,
} from '../lib/api'
import type { ApiError, Workflow } from '../lib/types'

interface UseWorkflowStateParams {
  token: string | null
  setLoading: (value: boolean) => void
  setError: (value: string | null) => void
  handleError: (error: ApiError) => void
}

interface UseWorkflowStateResult {
  workflows: Workflow[]
  activeWorkflowId: number | null
  setActiveWorkflowId: (workflowId: number | null) => void
  clearWorkflowState: () => void
  handleCreateWorkflow: (name: string) => Promise<void>
  handleRenameWorkflow: (workflowId: number, name: string) => Promise<void>
  handleDeleteWorkflow: (workflowId: number) => Promise<void>
}

export function useWorkflowState({
  token,
  setLoading,
  setError,
  handleError,
}: UseWorkflowStateParams): UseWorkflowStateResult {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [activeWorkflowId, setActiveWorkflowId] = useState<number | null>(null)

  useEffect(() => {
    if (!token) {
      setWorkflows([])
      setActiveWorkflowId(null)
      return
    }

    setLoading(true)
    void getWorkflows()
      .then((items) => {
        setWorkflows(items)
        setActiveWorkflowId((previous) => previous ?? items[0]?.id ?? null)
      })
      .catch((error: ApiError) => handleError(error))
      .finally(() => setLoading(false))
  }, [handleError, setLoading, token])

  const handleCreateWorkflow = useCallback(
    async (name: string): Promise<void> => {
      if (!name.trim()) {
        return
      }
      setLoading(true)
      try {
        const created = await createWorkflow(name.trim())
        setWorkflows((previous) => [created, ...previous])
        setActiveWorkflowId(created.id)
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, setError, setLoading],
  )

  const handleRenameWorkflow = useCallback(
    async (workflowId: number, name: string): Promise<void> => {
      setLoading(true)
      try {
        const updated = await updateWorkflow(workflowId, name)
        setWorkflows((previous) =>
          previous.map((workflow) =>
            workflow.id === workflowId ? updated : workflow,
          ),
        )
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, setError, setLoading],
  )

  const handleDeleteWorkflow = useCallback(
    async (workflowId: number): Promise<void> => {
      setLoading(true)
      try {
        await deleteWorkflow(workflowId)
        setWorkflows((previous) => {
          const next = previous.filter((workflow) => workflow.id !== workflowId)
          if (activeWorkflowId === workflowId) {
            setActiveWorkflowId(next[0]?.id ?? null)
          }
          return next
        })
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [activeWorkflowId, handleError, setError, setLoading],
  )

  const clearWorkflowState = useCallback(() => {
    setWorkflows([])
    setActiveWorkflowId(null)
  }, [])

  return {
    workflows,
    activeWorkflowId,
    setActiveWorkflowId,
    clearWorkflowState,
    handleCreateWorkflow,
    handleRenameWorkflow,
    handleDeleteWorkflow,
  }
}
