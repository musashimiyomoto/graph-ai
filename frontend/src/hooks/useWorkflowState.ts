import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  createWorkflow,
  deleteWorkflow,
  getWorkflows,
  updateWorkflow,
} from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
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
  const queryClient = useQueryClient()
  const [activeWorkflowId, setActiveWorkflowId] = useState<number | null>(null)

  const query = useQuery({
    queryKey: queryKeys.workflows(),
    queryFn: getWorkflows,
    enabled: token !== null,
  })
  const workflows = useMemo(
    () => (token !== null ? (query.data ?? []) : []),
    [token, query.data],
  )

  useEffect(() => {
    setLoading(query.isLoading)
  }, [query.isLoading, setLoading])

  useEffect(() => {
    if (query.error) {
      handleError(query.error)
    }
  }, [query.error, handleError])

  // Default to the first workflow once the list loads, but never override a
  // selection the user already made (including deliberately clearing it).
  useEffect(() => {
    if (!token) {
      setActiveWorkflowId(null)
      return
    }
    setActiveWorkflowId((previous) => previous ?? workflows[0]?.id ?? null)
  }, [token, workflows])

  const createMutation = useMutation({
    mutationFn: createWorkflow,
    onSuccess: (created) => {
      queryClient.setQueryData(
        queryKeys.workflows(),
        (previous: Workflow[] | undefined) => [created, ...(previous ?? [])],
      )
      setActiveWorkflowId(created.id)
    },
  })

  const renameMutation = useMutation({
    mutationFn: ({ workflowId, name }: { workflowId: number; name: string }) =>
      updateWorkflow(workflowId, name),
    onSuccess: (updated) => {
      queryClient.setQueryData(
        queryKeys.workflows(),
        (previous: Workflow[] | undefined) =>
          previous?.map((workflow) =>
            workflow.id === updated.id ? updated : workflow,
          ) ?? [],
      )
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteWorkflow,
    onSuccess: (_data, workflowId) => {
      queryClient.setQueryData(
        queryKeys.workflows(),
        (previous: Workflow[] | undefined) => {
          const next = previous?.filter((workflow) => workflow.id !== workflowId) ?? []
          setActiveWorkflowId((current) =>
            current === workflowId ? (next[0]?.id ?? null) : current,
          )
          return next
        },
      )
    },
  })

  const handleCreateWorkflow = useCallback(
    async (name: string): Promise<void> => {
      if (!name.trim()) {
        return
      }
      setLoading(true)
      try {
        await createMutation.mutateAsync(name.trim())
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [createMutation, handleError, setError, setLoading],
  )

  const handleRenameWorkflow = useCallback(
    async (workflowId: number, name: string): Promise<void> => {
      setLoading(true)
      try {
        await renameMutation.mutateAsync({ workflowId, name })
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, renameMutation, setError, setLoading],
  )

  const handleDeleteWorkflow = useCallback(
    async (workflowId: number): Promise<void> => {
      setLoading(true)
      try {
        await deleteMutation.mutateAsync(workflowId)
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [deleteMutation, handleError, setError, setLoading],
  )

  const clearWorkflowState = useCallback(() => {
    setActiveWorkflowId(null)
    queryClient.removeQueries({ queryKey: queryKeys.workflows() })
  }, [queryClient])

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
