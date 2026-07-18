import type { SVGProps } from 'react'

const SIZE = 18
const STYLE = { imageRendering: 'pixelated' as const }

type IconProps = SVGProps<SVGSVGElement>

export function InputIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="3" y="1" width="10" height="2" fill="var(--accent)" />
      <rect x="7" y="3" width="2" height="6" fill="var(--accent)" />
      <rect x="5" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="9" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="3" y="13" width="10" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function LlmIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
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

export function OutputIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="3" y="1" width="10" height="2" fill="var(--accent)" />
      <rect x="5" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="9" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="7" y="7" width="2" height="6" fill="var(--accent)" />
      <rect x="3" y="13" width="10" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function WebSearchIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="2" y="2" width="8" height="2" fill="var(--accent-2)" />
      <rect x="2" y="4" width="2" height="6" fill="var(--accent-2)" />
      <rect x="4" y="8" width="2" height="2" fill="var(--accent-2)" />
      <rect x="6" y="10" width="2" height="2" fill="var(--accent-2)" />
      <rect x="8" y="12" width="2" height="2" fill="var(--accent-2)" />
      <rect x="9" y="9" width="2" height="2" fill="var(--accent)" />
      <rect x="10" y="10" width="2" height="2" fill="var(--accent)" />
      <rect x="11" y="11" width="2" height="2" fill="var(--accent)" />
      <rect x="12" y="12" width="2" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function TemplateIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="2" y="2" width="12" height="2" fill="var(--accent-2)" />
      <rect x="2" y="4" width="2" height="10" fill="var(--accent-2)" />
      <rect x="12" y="4" width="2" height="10" fill="var(--accent-2)" />
      <rect x="2" y="12" width="12" height="2" fill="var(--accent-2)" />
      <rect x="5" y="6" width="6" height="2" fill="var(--accent)" />
      <rect x="5" y="9" width="4" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function HttpRequestIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="2" y="7" width="8" height="2" fill="var(--accent)" />
      <rect x="8" y="5" width="2" height="2" fill="var(--accent)" />
      <rect x="10" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="8" y="9" width="2" height="2" fill="var(--accent)" />
      <rect x="2" y="2" width="2" height="2" fill="var(--accent-2)" />
      <rect x="2" y="12" width="2" height="2" fill="var(--accent-2)" />
    </svg>
  )
}

export function CodeTransformIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="1" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="3" y="5" width="2" height="2" fill="var(--accent)" />
      <rect x="3" y="9" width="2" height="2" fill="var(--accent)" />
      <rect x="11" y="5" width="2" height="2" fill="var(--accent)" />
      <rect x="11" y="9" width="2" height="2" fill="var(--accent)" />
      <rect x="13" y="7" width="2" height="2" fill="var(--accent)" />
      <rect x="9" y="3" width="2" height="2" fill="var(--accent-2)" />
      <rect x="7" y="6" width="2" height="2" fill="var(--accent-2)" />
      <rect x="5" y="9" width="2" height="2" fill="var(--accent-2)" />
      <rect x="5" y="11" width="2" height="2" fill="var(--accent-2)" />
    </svg>
  )
}

export function ConditionIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="2" y="7" width="3" height="2" fill="var(--accent)" />
      <rect x="5" y="7" width="2" height="2" fill="var(--accent-2)" />
      <rect x="7" y="3" width="2" height="4" fill="var(--accent-2)" />
      <rect x="7" y="9" width="2" height="4" fill="var(--accent-2)" />
      <rect x="9" y="2" width="4" height="2" fill="var(--accent)" />
      <rect x="9" y="12" width="4" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function VectorIngestIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="7" y="1" width="2" height="5" fill="var(--accent-2)" />
      <rect x="5" y="5" width="2" height="2" fill="var(--accent-2)" />
      <rect x="9" y="5" width="2" height="2" fill="var(--accent-2)" />
      <rect x="7" y="7" width="2" height="2" fill="var(--accent-2)" />
      <rect x="2" y="10" width="2" height="4" fill="var(--accent)" />
      <rect x="12" y="10" width="2" height="4" fill="var(--accent)" />
      <rect x="2" y="13" width="12" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function VectorSearchIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="3" y="2" width="6" height="2" fill="var(--accent-2)" />
      <rect x="2" y="4" width="2" height="4" fill="var(--accent-2)" />
      <rect x="8" y="4" width="2" height="4" fill="var(--accent-2)" />
      <rect x="3" y="8" width="6" height="2" fill="var(--accent-2)" />
      <rect x="9" y="9" width="2" height="2" fill="var(--accent)" />
      <rect x="11" y="11" width="2" height="2" fill="var(--accent)" />
      <rect x="13" y="13" width="2" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function TableIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="1" y="2" width="14" height="2" fill="var(--accent-2)" />
      <rect x="1" y="7" width="14" height="2" fill="var(--accent)" />
      <rect x="1" y="12" width="14" height="2" fill="var(--accent-2)" />
      <rect x="1" y="2" width="2" height="12" fill="var(--accent-2)" />
      <rect x="7" y="2" width="2" height="12" fill="var(--accent)" />
      <rect x="13" y="2" width="2" height="12" fill="var(--accent-2)" />
    </svg>
  )
}

export function CallWorkflowIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="1" y="3" width="6" height="2" fill="var(--accent-2)" />
      <rect x="1" y="5" width="2" height="6" fill="var(--accent-2)" />
      <rect x="1" y="11" width="6" height="2" fill="var(--accent-2)" />
      <rect x="9" y="3" width="6" height="2" fill="var(--accent)" />
      <rect x="13" y="5" width="2" height="6" fill="var(--accent)" />
      <rect x="9" y="11" width="6" height="2" fill="var(--accent)" />
      <rect x="5" y="7" width="6" height="2" fill="var(--accent)" />
      <rect x="9" y="5" width="2" height="2" fill="var(--accent)" />
      <rect x="9" y="9" width="2" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function LoopIcon(props: IconProps) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" style={STYLE} fill="none" {...props}>
      <rect x="4" y="2" width="8" height="2" fill="var(--accent)" />
      <rect x="12" y="4" width="2" height="2" fill="var(--accent)" />
      <rect x="12" y="10" width="2" height="2" fill="var(--accent)" />
      <rect x="4" y="12" width="8" height="2" fill="var(--accent)" />
      <rect x="2" y="4" width="2" height="2" fill="var(--accent)" />
      <rect x="2" y="10" width="2" height="2" fill="var(--accent)" />
      <rect x="9" y="1" width="2" height="2" fill="var(--accent)" />
      <rect x="9" y="4" width="2" height="2" fill="var(--accent)" />
      <rect x="5" y="10" width="2" height="2" fill="var(--accent)" />
      <rect x="5" y="13" width="2" height="2" fill="var(--accent)" />
    </svg>
  )
}

export function NodeIcon({ iconKey }: { iconKey: string }) {
  if (iconKey === 'loop') {
    return <LoopIcon />
  }


  if (iconKey === 'llm') {
    return <LlmIcon />
  }

  if (iconKey === 'web_search') {
    return <WebSearchIcon />
  }

  if (iconKey === 'template') {
    return <TemplateIcon />
  }

  if (iconKey === 'http_request') {
    return <HttpRequestIcon />
  }

  if (iconKey === 'condition') {
    return <ConditionIcon />
  }

  if (iconKey === 'code_transform') {
    return <CodeTransformIcon />
  }

  if (iconKey === 'vector_ingest') {
    return <VectorIngestIcon />
  }

  if (iconKey === 'vector_search') {
    return <VectorSearchIcon />
  }

  if (iconKey === 'table') {
    return <TableIcon />
  }

  if (iconKey === 'call_workflow') {
    return <CallWorkflowIcon />
  }

  if (iconKey === 'output') {
    return <OutputIcon />
  }

  return <InputIcon />
}
