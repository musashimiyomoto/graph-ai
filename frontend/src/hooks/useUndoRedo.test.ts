import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { UndoableCommand } from './useUndoRedo'
import { useUndoRedo } from './useUndoRedo'

function makeCommand(label = 'cmd'): UndoableCommand {
  return {
    label,
    execute: vi.fn().mockResolvedValue(undefined),
    undo: vi.fn().mockResolvedValue(undefined),
  }
}

describe('useUndoRedo', () => {
  it('starts with nothing to undo or redo', () => {
    const { result } = renderHook(() => useUndoRedo())
    expect(result.current.canUndo).toBe(false)
    expect(result.current.canRedo).toBe(false)
  })

  it('pushCommand enables undo and clears any pending redo', () => {
    const { result } = renderHook(() => useUndoRedo())

    act(() => {
      result.current.pushCommand(makeCommand())
    })

    expect(result.current.canUndo).toBe(true)
    expect(result.current.canRedo).toBe(false)
  })

  it('undo calls the command undo and enables redo', async () => {
    const { result } = renderHook(() => useUndoRedo())
    const command = makeCommand()

    act(() => {
      result.current.pushCommand(command)
    })
    await act(async () => {
      await result.current.undo()
    })

    expect(command.undo).toHaveBeenCalledTimes(1)
    expect(result.current.canUndo).toBe(false)
    expect(result.current.canRedo).toBe(true)
  })

  it('redo re-executes the command and moves it back to the undo stack', async () => {
    const { result } = renderHook(() => useUndoRedo())
    const command = makeCommand()

    act(() => {
      result.current.pushCommand(command)
    })
    await act(async () => {
      await result.current.undo()
    })
    await act(async () => {
      await result.current.redo()
    })

    expect(command.execute).toHaveBeenCalledTimes(1)
    expect(result.current.canUndo).toBe(true)
    expect(result.current.canRedo).toBe(false)
  })

  it('pushing a new command after undo discards the redo future', async () => {
    const { result } = renderHook(() => useUndoRedo())

    act(() => {
      result.current.pushCommand(makeCommand('first'))
    })
    await act(async () => {
      await result.current.undo()
    })
    // A fresh command while a redo is pending should drop that redo.
    act(() => {
      result.current.pushCommand(makeCommand('second'))
    })

    expect(result.current.canRedo).toBe(false)
    expect(result.current.canUndo).toBe(true)
  })

  it('undo on an empty stack is a no-op', async () => {
    const { result } = renderHook(() => useUndoRedo())
    await act(async () => {
      await result.current.undo()
    })
    expect(result.current.canUndo).toBe(false)
    expect(result.current.canRedo).toBe(false)
  })

  it('clear resets both stacks', async () => {
    const { result } = renderHook(() => useUndoRedo())

    act(() => {
      result.current.pushCommand(makeCommand())
    })
    act(() => {
      result.current.clear()
    })

    expect(result.current.canUndo).toBe(false)
    expect(result.current.canRedo).toBe(false)
  })
})
