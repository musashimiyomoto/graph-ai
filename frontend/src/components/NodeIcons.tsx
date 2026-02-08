const SIZE = 18
const STYLE = { imageRendering: 'pixelated' as const }

export function InputIcon() {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none">
      <rect x="3" y="1" width="10" height="2" fill="var(--accent)" />
      <rect x="7" y="3" width="2" height="6" fill="var(--accent)" />
      <rect x="5" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="9" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="3" y="13" width="10" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function LlmIcon() {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none">
      <rect x="4" y="1" width="8" height="2" fill="var(--accent-2)" />
      <rect x="2" y="3" width="2" height="2" fill="var(--accent-2)" />
      <rect x="12" y="3" width="2" height="2" fill="var(--accent-2)" />
      <rect x="2" y="5" width="2" height="4" fill="var(--accent-2)" />
      <rect x="12" y="5" width="2" height="4" fill="var(--accent-2)" />
      <rect x="5" y="5" width="2" height="2" fill="var(--accent-2)" />
      <rect x="9" y="5" width="2" height="2" fill="var(--accent-2)" />
      <rect x="4" y="9" width="8" height="2" fill="var(--accent-2)" />
      <rect x="5" y="11" width="2" height="2" fill="var(--accent-2)" />
      <rect x="9" y="11" width="2" height="2" fill="var(--accent-2)" />
      <rect x="4" y="13" width="8" height="2" fill="var(--accent-2)" />
    </svg>
  )
}

export function OutputIcon() {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none">
      <rect x="3" y="1" width="10" height="2" fill="var(--accent)" />
      <rect x="5" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="9" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="7" y="7" width="2" height="6" fill="var(--accent)" />
      <rect x="3" y="13" width="10" height="2" fill="var(--accent)" />
    </svg>
  )
}
