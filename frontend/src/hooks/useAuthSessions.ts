import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { getAuthSessions, revokeAuthSession } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError, AuthSession } from '../lib/types'

export function useAuthSessions(onError: (error: ApiError) => void) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: queryKeys.authSessions(),
    queryFn: getAuthSessions,
  })
  const revokeMutation = useMutation({
    mutationFn: revokeAuthSession,
    onSuccess: (_data, sessionId) => {
      queryClient.setQueryData(
        queryKeys.authSessions(),
        (previous: AuthSession[] | undefined) =>
          previous?.filter((item) => item.id !== sessionId) ?? [],
      )
    },
  })

  useEffect(() => {
    if (query.error) {
      onError(query.error)
    }
  }, [onError, query.error])

  async function revoke(sessionId: number): Promise<boolean> {
    try {
      await revokeMutation.mutateAsync(sessionId)
      return true
    } catch (error) {
      onError(error as ApiError)
      return false
    }
  }

  return {
    sessions: query.data ?? [],
    loading: query.isLoading,
    revoking: revokeMutation.isPending,
    revoke,
  }
}
