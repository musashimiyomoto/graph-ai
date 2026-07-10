import { useCallback, useEffect, useRef, useState } from 'react'

import { getVectorJobStatus } from '../lib/api'
import type { ApiError } from '../lib/types'

export interface PendingUpload {
  jobId: string
  source: string
  collection: string
}

interface UseVectorUploadJobsParams {
  // Called once when any tracked upload finishes ingesting, so the caller can
  // refresh the collection/document lists.
  onReady: () => void
  onError: (error: ApiError) => void
}

interface UseVectorUploadJobsResult {
  pending: PendingUpload[]
  track: (upload: PendingUpload) => void
}

const POLL_INTERVAL_MS = 1500

// Ingestion runs on the ARQ worker after the upload POST returns, so we poll
// each job's status until it flips to ready/failed. Callbacks are held in refs
// so the polling effect only restarts when the pending set empties or fills,
// not on every parent re-render.
export function useVectorUploadJobs({
  onReady,
  onError,
}: UseVectorUploadJobsParams): UseVectorUploadJobsResult {
  const [pending, setPending] = useState<PendingUpload[]>([])

  const pendingRef = useRef<PendingUpload[]>([])
  const onReadyRef = useRef(onReady)
  const onErrorRef = useRef(onError)

  // Keep the refs current outside of render so the polling effect can read the
  // latest pending set and callbacks without restarting on every re-render.
  useEffect(() => {
    pendingRef.current = pending
    onReadyRef.current = onReady
    onErrorRef.current = onError
  })

  const track = useCallback((upload: PendingUpload): void => {
    setPending((previous) => [...previous, upload])
  }, [])

  const tick = useCallback(async (): Promise<void> => {
    await Promise.all(
      pendingRef.current.map(async (item) => {
        let status
        try {
          status = await getVectorJobStatus(item.jobId)
        } catch {
          // A transient poll failure — leave it pending and retry next tick.
          return
        }
        if (status.status === 'processing') {
          return
        }
        setPending((previous) => previous.filter((p) => p.jobId !== item.jobId))
        if (status.status === 'ready') {
          onReadyRef.current()
        } else {
          onErrorRef.current({
            message: status.detail ?? `Ingesting "${item.source}" failed.`,
            status: 0,
          })
        }
      }),
    )
  }, [])

  const active = pending.length > 0
  useEffect(() => {
    if (!active) {
      return
    }
    const id = window.setInterval(() => {
      void tick()
    }, POLL_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [active, tick])

  return { pending, track }
}
