import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import {
  duplicateWorkflow,
  exportWorkflow,
  importWorkflow,
  instantiateWorkflowTemplate,
} from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError, Workflow, WorkflowExport } from '../lib/types'

interface UseWorkflowTransferParams {
  setLoading: (value: boolean) => void
  setError: (value: string | null) => void
  handleError: (error: ApiError) => void
  onWorkflowCreated: (workflow: Workflow) => void
}

interface UseWorkflowTransferResult {
  handleDuplicateWorkflow: (workflowId: number) => Promise<void>
  handleExportWorkflow: (workflowId: number) => Promise<void>
  handleImportWorkflow: (file: File) => Promise<void>
  handleInstantiateTemplate: (
    templateKey: string,
    name?: string,
  ) => Promise<Workflow | null>
}

function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

// Sanitizes a workflow name into a safe filename fragment (matches the
// characters export-then-import round-trips through, without touching the
// name itself — only the download's local filename).
function toFilename(name: string): string {
  const safe = name.trim().replace(/[^a-z0-9-_]+/gi, '-').toLowerCase()
  return `${safe || 'workflow'}.json`
}

export function useWorkflowTransfer({
  setLoading,
  setError,
  handleError,
  onWorkflowCreated,
}: UseWorkflowTransferParams): UseWorkflowTransferResult {
  const queryClient = useQueryClient()

  const addWorkflowToCache = useCallback(
    (created: Workflow) => {
      queryClient.setQueryData(
        queryKeys.workflows(),
        (previous: Workflow[] | undefined) => [created, ...(previous ?? [])],
      )
      onWorkflowCreated(created)
    },
    [onWorkflowCreated, queryClient],
  )

  const handleDuplicateWorkflow = useCallback(
    async (workflowId: number): Promise<void> => {
      setLoading(true)
      try {
        const created = await duplicateWorkflow(workflowId)
        addWorkflowToCache(created)
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [addWorkflowToCache, handleError, setError, setLoading],
  )

  const handleExportWorkflow = useCallback(
    async (workflowId: number): Promise<void> => {
      setLoading(true)
      try {
        const data = await exportWorkflow(workflowId)
        downloadJson(toFilename(data.name), data)
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, setError, setLoading],
  )

  const handleImportWorkflow = useCallback(
    async (file: File): Promise<void> => {
      setLoading(true)
      try {
        const text = await file.text()
        let parsed: WorkflowExport
        try {
          parsed = JSON.parse(text) as WorkflowExport
        } catch {
          handleError({ message: 'Not a valid workflow export file.', status: 0 })
          return
        }
        const created = await importWorkflow(parsed.name, parsed.graph)
        addWorkflowToCache(created)
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [addWorkflowToCache, handleError, setError, setLoading],
  )

  const handleInstantiateTemplate = useCallback(
    async (templateKey: string, name?: string): Promise<Workflow | null> => {
      setLoading(true)
      try {
        const created = await instantiateWorkflowTemplate(templateKey, name)
        addWorkflowToCache(created)
        setError(null)
        return created
      } catch (error) {
        handleError(error as ApiError)
        return null
      } finally {
        setLoading(false)
      }
    },
    [addWorkflowToCache, handleError, setError, setLoading],
  )

  return {
    handleDuplicateWorkflow,
    handleExportWorkflow,
    handleImportWorkflow,
    handleInstantiateTemplate,
  }
}
