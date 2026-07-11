import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  createTelegramBot,
  deleteTelegramBot,
  getTelegramBots,
} from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type {
  ApiError,
  TelegramBot,
  TelegramBotCreatePayload,
} from '../lib/types'

interface UseTelegramBotsParams {
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseTelegramBotsResult {
  bots: TelegramBot[]
  loading: boolean
  creating: boolean
  refreshBots: () => Promise<void>
  createBot: (
    payload: TelegramBotCreatePayload,
  ) => Promise<TelegramBot | null>
  removeBot: (botId: number) => Promise<boolean>
}

// Shares one cached list across every consumer (Settings' bot list and
// NodeFieldsForm's bot picker both read/invalidate the same query key), so
// creating/deleting a bot in one place is immediately reflected in the
// other instead of each hook instance holding its own stale copy.
export function useTelegramBots({
  enabled = true,
  onError,
}: UseTelegramBotsParams): UseTelegramBotsResult {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: queryKeys.telegramBots(),
    queryFn: getTelegramBots,
    enabled,
  })

  const createMutation = useMutation({
    mutationFn: createTelegramBot,
    onSuccess: (created) => {
      queryClient.setQueryData(
        queryKeys.telegramBots(),
        (previous: TelegramBot[] | undefined) => [...(previous ?? []), created],
      )
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTelegramBot,
    onSuccess: (_data, botId) => {
      queryClient.setQueryData(
        queryKeys.telegramBots(),
        (previous: TelegramBot[] | undefined) =>
          previous?.filter((item) => item.id !== botId) ?? [],
      )
    },
  })

  async function createBot(
    payload: TelegramBotCreatePayload,
  ): Promise<TelegramBot | null> {
    try {
      return await createMutation.mutateAsync(payload)
    } catch (error) {
      onError?.(error as ApiError)
      return null
    }
  }

  async function removeBot(botId: number): Promise<boolean> {
    try {
      await deleteMutation.mutateAsync(botId)
      return true
    } catch (error) {
      onError?.(error as ApiError)
      return false
    }
  }

  useEffect(() => {
    if (query.error) {
      onError?.(query.error)
    }
  }, [query.error, onError])

  return {
    bots: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
    creating: createMutation.isPending,
    refreshBots: async () => {
      await query.refetch()
    },
    createBot,
    removeBot,
  }
}
