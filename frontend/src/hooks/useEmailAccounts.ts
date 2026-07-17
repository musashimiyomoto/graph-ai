import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  createEmailAccount,
  deleteEmailAccount,
  getEmailAccounts,
} from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type {
  ApiError,
  EmailAccount,
  EmailAccountCreatePayload,
} from '../lib/types'

interface UseEmailAccountsParams {
  enabled?: boolean
  onError?: (error: ApiError) => void
}

interface UseEmailAccountsResult {
  accounts: EmailAccount[]
  loading: boolean
  creating: boolean
  createAccount: (payload: EmailAccountCreatePayload) => Promise<EmailAccount | null>
  removeAccount: (accountId: number) => Promise<boolean>
}

export function useEmailAccounts({
  enabled = true,
  onError,
}: UseEmailAccountsParams): UseEmailAccountsResult {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: queryKeys.emailAccounts(),
    queryFn: getEmailAccounts,
    enabled,
  })
  const createMutation = useMutation({
    mutationFn: createEmailAccount,
    onSuccess: (created) => {
      queryClient.setQueryData(
        queryKeys.emailAccounts(),
        (previous: EmailAccount[] | undefined) => [...(previous ?? []), created],
      )
    },
  })
  const deleteMutation = useMutation({
    mutationFn: deleteEmailAccount,
    onSuccess: (_data, accountId) => {
      queryClient.setQueryData(
        queryKeys.emailAccounts(),
        (previous: EmailAccount[] | undefined) =>
          previous?.filter((account) => account.id !== accountId) ?? [],
      )
    },
  })

  useEffect(() => {
    if (query.error) {
      onError?.(query.error)
    }
  }, [query.error, onError])

  async function createAccount(
    payload: EmailAccountCreatePayload,
  ): Promise<EmailAccount | null> {
    try {
      return await createMutation.mutateAsync(payload)
    } catch (error) {
      onError?.(error as ApiError)
      return null
    }
  }

  async function removeAccount(accountId: number): Promise<boolean> {
    try {
      await deleteMutation.mutateAsync(accountId)
      return true
    } catch (error) {
      onError?.(error as ApiError)
      return false
    }
  }

  return {
    accounts: enabled ? (query.data ?? []) : [],
    loading: enabled && query.isLoading,
    creating: createMutation.isPending,
    createAccount,
    removeAccount,
  }
}
