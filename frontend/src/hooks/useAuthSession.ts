import { useCallback, useEffect, useRef, useState } from 'react'

import {
  deleteMe,
  getMe,
  login,
  logoutSession,
  refreshSession,
  register,
  requestPasswordReset,
  resendEmailVerification,
  resetPassword,
  setToken,
  verifyEmail,
} from '../lib/api'
import type { ApiError } from '../lib/types'

interface UseAuthSessionParams {
  setLoading: (value: boolean) => void
  setError: (value: string | null) => void
}

interface UseAuthSessionResult {
  token: string | null
  email: string
  authNotice: string | null
  pendingVerificationEmail: string | null
  resetPasswordToken: string | null
  handleError: (error: ApiError) => void
  handleLogin: (email: string, password: string) => Promise<void>
  handleRegister: (email: string, password: string) => Promise<void>
  handleResendVerification: (email: string) => Promise<void>
  handleRequestPasswordReset: (email: string) => Promise<void>
  handleResetPassword: (password: string) => Promise<void>
  clearAuthNotice: () => void
  handleLogout: () => void
  handlePasswordChanged: () => void
  handleDeleteAccount: () => Promise<void>
}

export function useAuthSession({
  setLoading,
  setError,
}: UseAuthSessionParams): UseAuthSessionResult {
  const [token, setTokenState] = useState<string | null>(null)
  const [email, setEmail] = useState<string>('')
  const [authNotice, setAuthNotice] = useState<string | null>(null)
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState<
    string | null
  >(null)
  const [resetPasswordToken, setResetPasswordToken] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get('reset_password_token'),
  )
  const handledVerificationLink = useRef(false)

  const handleLogout = useCallback((): void => {
    void logoutSession().catch(() => undefined)
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
    const params = new URLSearchParams(window.location.search)
    const verificationToken = params.get('verify_email_token')
    if (!verificationToken || handledVerificationLink.current) {
      return
    }
    handledVerificationLink.current = true

    setLoading(true)
    void verifyEmail(verificationToken)
      .then((response) => {
        setAuthNotice(`${response.detail}. You can sign in now.`)
        setError(null)
      })
      .catch((error: ApiError) => setError(error.message))
      .finally(() => {
        params.delete('verify_email_token')
        const query = params.toString()
        window.history.replaceState(
          {},
          '',
          `${window.location.pathname}${query ? `?${query}` : ''}`,
        )
        setLoading(false)
      })
  }, [setError, setLoading])

  useEffect(() => {
    // A recovery link must show the reset form even when the browser still
    // has a valid refresh cookie for an existing session.
    if (resetPasswordToken) {
      return
    }
    setLoading(true)
    void refreshSession()
      .then((response) => {
        if (response) {
          setTokenState(response.access_token)
        }
      })
      .finally(() => setLoading(false))
  }, [resetPasswordToken, setLoading])

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
        setTokenState(response.access_token)
        setAuthNotice(null)
        setPendingVerificationEmail(null)
        setError(null)
      } catch (error) {
        const issue = error as ApiError
        if (issue.status === 403) {
          setPendingVerificationEmail(emailValue)
        }
        // A rejected login is a form error, not an expired authenticated
        // session; keep it visible instead of routing it through logout.
        setError(issue.message)
      } finally {
        setLoading(false)
      }
    },
    [setError, setLoading],
  )

  const handleRegister = useCallback(
    async (emailValue: string, password: string): Promise<void> => {
      setLoading(true)
      try {
        await register(emailValue, password)
        setPendingVerificationEmail(emailValue)
        setAuthNotice('Account created. Check your inbox to verify your email.')
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, setError, setLoading],
  )

  const handleResendVerification = useCallback(
    async (emailValue: string): Promise<void> => {
      setLoading(true)
      try {
        const response = await resendEmailVerification(emailValue)
        setAuthNotice(response.detail)
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, setError, setLoading],
  )

  const handleRequestPasswordReset = useCallback(
    async (emailValue: string): Promise<void> => {
      setLoading(true)
      try {
        const response = await requestPasswordReset(emailValue)
        setAuthNotice(response.detail)
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, setError, setLoading],
  )

  const handleResetPassword = useCallback(
    async (password: string): Promise<void> => {
      if (!resetPasswordToken) {
        return
      }
      setLoading(true)
      try {
        const response = await resetPassword(resetPasswordToken, password)
        setResetPasswordToken(null)
        setAuthNotice(`${response.detail}. Sign in with your new password.`)
        setError(null)
        const params = new URLSearchParams(window.location.search)
        params.delete('reset_password_token')
        const query = params.toString()
        window.history.replaceState(
          {},
          '',
          `${window.location.pathname}${query ? `?${query}` : ''}`,
        )
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, resetPasswordToken, setError, setLoading],
  )

  const handleDeleteAccount = useCallback(async (): Promise<void> => {
    try {
      await deleteMe()
      handleLogout()
    } catch (error) {
      setError((error as ApiError).message)
    }
  }, [handleLogout, setError])

  const handlePasswordChanged = useCallback((): void => {
    handleLogout()
    setAuthNotice('Password changed. Sign in again with your new password.')
  }, [handleLogout])

  return {
    token,
    email,
    authNotice,
    pendingVerificationEmail,
    resetPasswordToken,
    handleError,
    handleLogin,
    handleRegister,
    handleResendVerification,
    handleRequestPasswordReset,
    handleResetPassword,
    clearAuthNotice: () => setAuthNotice(null),
    handleLogout,
    handlePasswordChanged,
    handleDeleteAccount,
  }
}
