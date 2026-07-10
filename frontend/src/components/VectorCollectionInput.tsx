import { useEffect, useRef, useState } from 'react'

import type { VectorCollection } from '../lib/types'

interface VectorCollectionInputProps {
  collections: VectorCollection[]
  value: string
  onChange: (value: string) => void
  placeholder?: string | null
}

// A themed combobox rather than a strict <select> or a native <datalist>:
// unlike providers/models/bots, a collection isn't a pre-existing entity you
// must pick — typing a name that doesn't exist yet is how a new collection gets
// created. This keeps that free-text path while surfacing existing collections
// in a dropdown that matches the pixel theme (the native <datalist> popup can't
// be styled). Shared by the node config form (Vector Ingest/Search) and the
// Vector Collections upload panel.
export function VectorCollectionInput({
  collections,
  value,
  onChange,
  placeholder,
}: VectorCollectionInputProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close the dropdown when clicking outside the combobox.
  useEffect(() => {
    if (!open) {
      return
    }
    function handlePointerDown(event: MouseEvent): void {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [open])

  const trimmed = value.trim()
  const query = trimmed.toLowerCase()
  const matches = collections.filter((collection) =>
    collection.name.toLowerCase().includes(query),
  )
  const isExisting = collections.some((collection) => collection.name === trimmed)
  const showCreate = trimmed.length > 0 && !isExisting

  function select(name: string): void {
    onChange(name)
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="pixel-combobox">
      <input
        className="pixel-input"
        value={value}
        placeholder={placeholder ?? ''}
        onChange={(event) => {
          onChange(event.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setOpen(false)
          }
        }}
      />
      {open && (matches.length > 0 || showCreate) ? (
        <ul className="pixel-combobox-menu">
          {matches.map((collection) => (
            <li key={collection.name}>
              <button
                type="button"
                className="pixel-combobox-option"
                onClick={() => select(collection.name)}
              >
                <span>{collection.name}</span>
                <span className="text-xs text-[var(--muted)]">
                  {collection.point_count} chunk
                  {collection.point_count === 1 ? '' : 's'}
                </span>
              </button>
            </li>
          ))}
          {showCreate ? (
            <li>
              <button
                type="button"
                className="pixel-combobox-option create"
                onClick={() => setOpen(false)}
              >
                + Create “{trimmed}”
              </button>
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  )
}
