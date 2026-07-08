import { useCallback, useRef, useState } from 'react'

export interface UndoableCommand {
  label: string
  execute: () => Promise<void>
  undo: () => Promise<void>
}

interface UseUndoRedoResult {
  canUndo: boolean
  canRedo: boolean
  pushCommand: (command: UndoableCommand) => void
  undo: () => Promise<void>
  redo: () => Promise<void>
  clear: () => void
}

// Nodes/edges get server-assigned IDs, so undo/redo can't be a client-side
// snapshot diff — it's a stack of commands that replay the same
// create/delete/update API calls in reverse. `past`/`future` are refs (not
// state) since only their *lengths* need to drive re-renders (canUndo/
// canRedo); the commands themselves never need to trigger a render on their
// own.
export function useUndoRedo(): UseUndoRedoResult {
  const past = useRef<UndoableCommand[]>([])
  const future = useRef<UndoableCommand[]>([])
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)

  const syncFlags = useCallback(() => {
    setCanUndo(past.current.length > 0)
    setCanRedo(future.current.length > 0)
  }, [])

  const pushCommand = useCallback(
    (command: UndoableCommand) => {
      past.current.push(command)
      future.current = []
      syncFlags()
    },
    [syncFlags],
  )

  const undo = useCallback(async (): Promise<void> => {
    const command = past.current.pop()
    if (!command) {
      return
    }
    await command.undo()
    future.current.push(command)
    syncFlags()
  }, [syncFlags])

  const redo = useCallback(async (): Promise<void> => {
    const command = future.current.pop()
    if (!command) {
      return
    }
    await command.execute()
    past.current.push(command)
    syncFlags()
  }, [syncFlags])

  const clear = useCallback(() => {
    past.current = []
    future.current = []
    syncFlags()
  }, [syncFlags])

  return { canUndo, canRedo, pushCommand, undo, redo, clear }
}
