const NUMBER_STEP = 0.1

interface NumberInputProps {
  displayValue: number | ''
  placeholder?: string
  min?: number
  max?: number
  onChangeRaw: (raw: string) => void
}

export function NumberInput({
  displayValue,
  placeholder,
  min,
  max,
  onChangeRaw,
}: NumberInputProps) {
  function clamp(next: number): number {
    let result = next
    if (min !== undefined) {
      result = Math.max(min, result)
    }
    if (max !== undefined) {
      result = Math.min(max, result)
    }
    return result
  }

  function stepBy(direction: number): void {
    const base = displayValue === '' ? min ?? 0 : displayValue
    const next = clamp(Number((base + direction * NUMBER_STEP).toFixed(4)))
    onChangeRaw(String(next))
  }

  function handleBlur(): void {
    if (displayValue === '' || Number.isNaN(displayValue)) {
      return
    }
    const clamped = clamp(displayValue)
    if (clamped !== displayValue) {
      onChangeRaw(String(clamped))
    }
  }

  return (
    <div className="relative">
      <input
        className="pixel-input no-spinner pr-8"
        type="number"
        value={displayValue}
        placeholder={placeholder ?? ''}
        min={min}
        max={max}
        step={NUMBER_STEP}
        onChange={(event) => onChangeRaw(event.target.value)}
        onBlur={handleBlur}
      />
      <div className="pixel-stepper">
        <button
          type="button"
          className="pixel-step"
          tabIndex={-1}
          aria-label="Increment"
          onClick={() => stepBy(1)}
        >
          ▲
        </button>
        <button
          type="button"
          className="pixel-step"
          tabIndex={-1}
          aria-label="Decrement"
          onClick={() => stepBy(-1)}
        >
          ▼
        </button>
      </div>
    </div>
  )
}
