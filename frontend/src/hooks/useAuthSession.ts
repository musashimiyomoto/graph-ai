import { useCallback, useEffect, useState } from 'react'

import { deleteMe, getMe, login, register, setToken } from '../lib/api'
import type { ApiError } from '../lib/types'

const TOKEN_KEY = 'graph_ai_token'

interface UseAuthSessionParams {
  setLoading: (value: boolean) => void
  setError: (value: string | null) => void
}

interface UseAuthSessionResult {
  token: string | null
  email: string
  handleError: (error: ApiError) => void
  handleLogin: (email: string, password: string) => Promise<void>
  handleRegister: (email: string, password: string) => Promise<void>
  handleLogout: () => void
  handleDeleteAccount: () => Promise<void>
}

export function useAuthSession({
  setLoading,
  setError,
}: UseAuthSessionParams): UseAuthSessionResult {
  const [token, setTokenState] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY),
  )
  const [email, setEmail] = useState<string>('')

  const handleLogout = useCallback((): void => {
    localStorage.removeItem(TOKEN_KEY)
    setTokenState(null)
    setEmail('')
    setError(null)
  }, [setError])

  const handleError = useCallback(
    (error: ApiError): void => {
      if (error.status === 401) {
        handleLogout()
        return
      }
      setError(error.message)
    },
    [handleLogout, setError],
  )

  useEffect(() => {
    setToken(token)
  }, [token])

  useEffect(() => {
    if (!token) {
      return
    }

    setLoading(true)
    void getMe()
      .then((profile) => setEmail(profile.email))
      .catch((error: ApiError) => handleError(error))
      .finally(() => setLoading(false))
  }, [handleError, setLoading, token])

  const handleLogin = useCallback(
    async (emailValue: string, password: string): Promise<void> => {
      setLoading(true)
      try {
        const response = await login(emailValue, password)
        localStorage.setItem(TOKEN_KEY, response.access_token)
        setTokenState(response.access_token)
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, setError, setLoading],
  )

  const handleRegister = useCallback(
    async (emailValue: string, password: string): Promise<void> => {
      setLoading(true)
      try {
        await register(emailValue, password)
        await handleLogin(emailValue, password)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, handleLogin, setLoading],
  )

  const handleDeleteAccount = useCallback(async (): Promise<void> => {
    try {
      await deleteMe()
      handleLogout()
    } catch (error) {
      setError((error as ApiError).message)
    }
  }, [handleLogout, setError])

  return {
    token,
    email,
    handleError,
    handleLogin,
    handleRegister,
    handleLogout,
    handleDeleteAccount,
  }
}
