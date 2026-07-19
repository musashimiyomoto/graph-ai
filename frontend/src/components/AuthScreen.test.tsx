import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AuthScreen } from './AuthScreen'

function renderScreen(
  overrides: Partial<React.ComponentProps<typeof AuthScreen>> = {},
) {
  const props: React.ComponentProps<typeof AuthScreen> = {
    loading: false,
    error: null,
    notice: null,
    pendingVerificationEmail: null,
    resetPasswordToken: null,
    onLogin: vi.fn(),
    onRegister: vi.fn(),
    onResendVerification: vi.fn(),
    onRequestPasswordReset: vi.fn(),
    onResetPassword: vi.fn(),
    onClearNotice: vi.fn(),
    ...overrides,
  }
  render(<AuthScreen {...props} />)
  return props
}

describe('AuthScreen', () => {
  it('opens recovery mode and requests a reset for the entered email', async () => {
    const user = userEvent.setup()
    const props = renderScreen()

    await user.click(screen.getByRole('button', { name: 'Forgot password?' }))
    await user.type(screen.getByLabelText('Email'), 'person@example.com')
    await user.click(screen.getByRole('button', { name: 'Send Reset Link' }))

    expect(props.onRequestPasswordReset).toHaveBeenCalledWith('person@example.com')
  })

  it('validates matching passwords before consuming a reset link', async () => {
    const user = userEvent.setup()
    const props = renderScreen({ resetPasswordToken: 'reset-token' })

    await user.type(screen.getByLabelText('New password'), 'new-password')
    await user.type(screen.getByLabelText('Confirm password'), 'different-password')
    await user.click(screen.getByRole('button', { name: 'Reset Password' }))

    expect(screen.getByText('Passwords do not match.')).toBeInTheDocument()
    expect(props.onResetPassword).not.toHaveBeenCalled()
  })

  it('offers a verification resend for the blocked account', async () => {
    const user = userEvent.setup()
    const props = renderScreen({
      pendingVerificationEmail: 'unverified@example.com',
      error: 'Verify your email before signing in',
    })

    await user.click(
      screen.getByRole('button', { name: 'Resend verification email' }),
    )

    expect(props.onResendVerification).toHaveBeenCalledWith(
      'unverified@example.com',
    )
  })
})
