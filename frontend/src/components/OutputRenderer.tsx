import type { ReactNode } from 'react'

import type { NodeValueEnvelope } from '../lib/types'
import { ArtifactOutput } from './ArtifactOutput'

function renderText(value: string): ReactNode {
  return <div className="whitespace-pre-wrap">{value}</div>
}

function renderJson(value: unknown): ReactNode {
  return (
    <pre className="hide-scrollbar max-h-64 overflow-auto text-xs">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

interface OutputRendererProps {
  typedValue: NodeValueEnvelope
}

export function OutputRenderer({ typedValue }: OutputRendererProps) {
  if (typedValue.artifact) {
    return <ArtifactOutput artifact={typedValue.artifact} kind={typedValue.kind} />
  }
  if (typedValue.kind === 'json' || typedValue.kind === 'list') {
    return <>{renderJson(typedValue.value)}</>
  }
  return <>{renderText(typeof typedValue.value === 'string' ? typedValue.value : '')}</>
}
