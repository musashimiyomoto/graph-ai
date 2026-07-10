const DEFAULT_STEP = 0.1

interface NumberInputProps {
  displayValue: number | ''
  placeholder?: string
  min?: number
  max?: number
  step?: number
  onChangeRaw: (raw: string) => void
}

export function NumberInput({
  displayValue,
  placeholder,
  min,
  max,
  step = DEFAULT_STEP,
  onChangeRaw,
}: NumberInputProps) {
  // Round to the step's own precision so an integer step (1) never yields a
  // fractional value and a 0.1 step doesn't drift into float noise.
  const decimals = Number.isInteger(step) ? 0 : String(step).split('.')[1].length

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
    const next = clamp(Number((base + direction * step).toFixed(decimals)))
    onChangeRaw(String(next))
  }

  function handleBlur(): void {
    if (displayValue === '' || Number.isNaN(displayValue)) {
      return
    }
    // Snap integer-stepped fields (top_k, max_tokens, …) to a whole number so a
    // manually typed decimal can't slip through; leave float fields untouched.
    let result = clamp(displayValue)
    if (Number.isInteger(step)) {
      result = Math.round(result)
    }
    if (result !== displayValue) {
      onChangeRaw(String(result))
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
        step={step}
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
