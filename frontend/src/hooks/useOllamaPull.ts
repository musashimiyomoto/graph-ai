import { useCallback, useEffect, useRef, useState } from 'react'

import { pullOllamaModel, streamOllamaPull } from '../lib/api'
import type { ApiError } from '../lib/types'

export interface PullProgress {
  model: string
  status: string
  percent: number | null
}

interface UseOllamaPullParams {
  providerId: number
  onDone: () => void
  onError: (error: ApiError) => void
}

interface UseOllamaPullResult {
  pull: PullProgress | null
  startPull: (model: string) => Promise<void>
}

// Starts an Ollama model pull and follows its live SSE progress. Aborts the
// stream on unmount; callbacks are held in refs so the abort effect stays
// stable.
export function useOllamaPull({
  providerId,
  onDone,
  onError,
}: UseOllamaPullParams): UseOllamaPullResult {
  const [pull, setPull] = useState<PullProgress | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const onDoneRef = useRef(onDone)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onDoneRef.current = onDone
    onErrorRef.current = onError
  })

  useEffect(() => () => abortRef.current?.abort(), [])

  const startPull = useCallback(
    async (model: string): Promise<void> => {
      const trimmed = model.trim()
      if (!trimmed) {
        return
      }
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setPull({ model: trimmed, status: 'queued', percent: null })

      try {
        const job = await pullOllamaModel(providerId, trimmed)
        await streamOllamaPull(
          providerId,
          job.job_id,
          (event) => {
            if (event.error) {
              setPull(null)
              onErrorRef.current({ message: event.error, status: 0 })
              return
            }
            setPull({
              model: trimmed,
              status: event.status,
              percent: event.percent ?? null,
            })
            if (event.done) {
              setPull(null)
              onDoneRef.current()
            }
          },
          controller.signal,
        )
      } catch (error) {
        if (controller.signal.aborted) {
          return
        }
        setPull(null)
        onErrorRef.current(error as ApiError)
      }
    },
    [providerId],
  )

  return { pull, startPull }
}
