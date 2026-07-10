import { useEffect, useRef, useState } from 'react'

import type { LlmModel, OllamaCatalogEntry } from '../lib/types'

interface OllamaModelPickerProps {
  catalog: OllamaCatalogEntry[]
  installed: LlmModel[]
  value: string
  onChange: (value: string) => void
}

interface PickerOption {
  tag: string
  sub: string
  installed: boolean
}

// Combobox seeded from the curated catalog (Ollama has no registry-listing API),
// flagging already-installed tags, while free-text stays allowed for any model
// not in the catalog. Shares the `.pixel-combobox` styling with the collection
// picker.
export function OllamaModelPicker({
  catalog,
  installed,
  value,
  onChange,
}: OllamaModelPickerProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

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

  const installedNames = new Set(installed.map((model) => model.name))
  const options: PickerOption[] = catalog.flatMap((entry) =>
    entry.tags.map((tag) => ({
      tag: tag.tag,
      sub: `${tag.params} · ${tag.size_gb} GB`,
      installed: installedNames.has(tag.tag),
    })),
  )
  const query = value.trim().toLowerCase()
  const matches = options.filter(
    (option) =>
      option.tag.toLowerCase().includes(query) ||
      option.sub.toLowerCase().includes(query),
  )

  return (
    <div ref={containerRef} className="pixel-combobox">
      <input
        className="pixel-input"
        value={value}
        placeholder="llama3.2:1b"
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
      {open && matches.length > 0 ? (
        <ul className="pixel-combobox-menu">
          {matches.map((option) => (
            <li key={option.tag}>
              <button
                type="button"
                className="pixel-combobox-option"
                onClick={() => {
                  onChange(option.tag)
                  setOpen(false)
                }}
              >
                <span>
                  {option.tag}
                  {option.installed ? ' · installed' : ''}
                </span>
                <span className="text-xs text-[var(--muted)]">{option.sub}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
