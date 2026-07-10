import { useId } from 'react'

import type { VectorCollection } from '../lib/types'

interface VectorCollectionInputProps {
  collections: VectorCollection[]
  value: string
  onChange: (value: string) => void
  placeholder?: string | null
}

// A datalist-backed text input rather than a strict <select>: unlike
// providers/models/bots, a collection isn't a pre-existing entity you must
// pick — typing a name that doesn't exist yet is how a new collection gets
// created. This keeps that free-text path while still surfacing existing
// collections so the user isn't typing blind. Shared by the node config form
// (Vector Ingest/Search) and the Vector Collections upload panel.
export function VectorCollectionInput({
  collections,
  value,
  onChange,
  placeholder,
}: VectorCollectionInputProps) {
  const datalistId = useId()

  return (
    <>
      <input
        className="pixel-input"
        list={datalistId}
        value={value}
        placeholder={placeholder ?? ''}
        onChange={(event) => onChange(event.target.value)}
      />
      <datalist id={datalistId}>
        {collections.map((collection) => (
          <option key={collection.name} value={collection.name} />
        ))}
      </datalist>
    </>
  )
}
