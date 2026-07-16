import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Modal } from './Modal'

describe('Modal', () => {
  it('renders as an accessible dialog', () => {
    render(
      <Modal onClose={vi.fn()}>
        <p>content</p>
      </Modal>,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn()
    render(
      <Modal onClose={onClose}>
        <p>content</p>
      </Modal>,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when clicking outside the panel', () => {
    const onClose = vi.fn()
    render(
      <Modal onClose={onClose}>
        <p>content</p>
      </Modal>,
    )
    // mousedown on the backdrop (outside the dialog panel) closes it.
    fireEvent.mouseDown(document.body)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not call onClose when clicking inside the panel', () => {
    const onClose = vi.fn()
    render(
      <Modal onClose={onClose}>
        <button type="button">inside</button>
      </Modal>,
    )
    fireEvent.mouseDown(screen.getByText('inside'))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('auto-focuses the first focusable element on mount', () => {
    render(
      <Modal onClose={vi.fn()}>
        <button type="button">first</button>
        <button type="button">second</button>
      </Modal>,
    )
    expect(screen.getByText('first')).toHaveFocus()
  })

  it('traps Tab focus from the last element back to the first', () => {
    render(
      <Modal onClose={vi.fn()}>
        <button type="button">first</button>
        <button type="button">last</button>
      </Modal>,
    )
    const last = screen.getByText('last')
    last.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(screen.getByText('first')).toHaveFocus()
  })
})
