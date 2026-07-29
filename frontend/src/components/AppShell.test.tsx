import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AppShell } from './AppShell'

const BASE_PROPS = {
  email: 'person@example.com',
  workflowName: 'Demo workflow',
  workflowBreadcrumbs: [],
  onNavigateBreadcrumb: vi.fn(),
  showInspector: false,
  error: null,
  canUndo: true,
  canRedo: false,
  onUndo: vi.fn(),
  onRedo: vi.fn(),
  onAutoLayout: vi.fn(),
  onDismissError: vi.fn(),
}

describe('AppShell', () => {
  it('uses persistent workspace navigation instead of opening overlays', async () => {
    const user = userEvent.setup()
    const onChangeView = vi.fn()

    render(
      <AppShell
        {...BASE_PROPS}
        activeView="editor"
        onChangeView={onChangeView}
      >
        <div>Editor content</div>
      </AppShell>,
    )

    expect(screen.getByRole('button', { name: 'Editor' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await user.click(screen.getByRole('button', { name: 'Profile' }))
    expect(onChangeView).toHaveBeenCalledWith('profile')
  })

  it('keeps editor controls out of non-editor pages', () => {
    render(
      <AppShell
        {...BASE_PROPS}
        activeView="profile"
        onChangeView={vi.fn()}
      >
        <div>Profile content</div>
      </AppShell>,
    )

    expect(screen.getByRole('button', { name: 'Profile' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument()
  })
})
