import type { Node as FlowNode } from 'reactflow'

interface InspectorPanelProps {
  node: FlowNode | null
  runInput: string
  onChangeRunInput: (value: string) => void
  onSaveNode: (id: string, data: Record<string, unknown>) => void
}

export function InspectorPanel({
  node,
  runInput,
  onChangeRunInput,
  onSaveNode,
}: InspectorPanelProps) {
  const nodeType = (node?.data?.nodeType as string | undefined) ?? 'INPUT'
  const nodeData = (node?.data as Record<string, unknown>) ?? {}

  function updateField(key: string, value: string | number) {
    if (!node) {
      return
    }
    const updated = { ...nodeData, [key]: value }
    onSaveNode(node.id, updated)
  }

  return (
    <aside className="pixel-panel flex h-full flex-col gap-6">
      <div>
        <div className="pixel-section-title">Inspector</div>
        {!node ? (
          <div className="mt-4 text-xs text-[var(--muted)]">
            Выбери ноду, чтобы настроить её параметры.
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-3">
            <div className="text-xs text-[var(--muted)]">
              Тип: <span className="text-[var(--accent)]">{nodeType}</span>
            </div>
            <label className="pixel-label">
              Label
              <input
                className="pixel-input"
                value={(nodeData.label as string) ?? ''}
                onChange={(event) => updateField('label', event.target.value)}
              />
            </label>
            {nodeType === 'INPUT' ? (
              <label className="pixel-label">
                Sample Input
                <textarea
                  className="pixel-textarea"
                  value={(nodeData.sample_input as string) ?? ''}
                  onChange={(event) =>
                    updateField('sample_input', event.target.value)
                  }
                />
              </label>
            ) : null}
            {nodeType === 'LLM' ? (
              <>
                <label className="pixel-label">
                  Model
                  <input
                    className="pixel-input"
                    value={(nodeData.model as string) ?? ''}
                    onChange={(event) => updateField('model', event.target.value)}
                  />
                </label>
                <label className="pixel-label">
                  Prompt
                  <textarea
                    className="pixel-textarea"
                    value={(nodeData.prompt as string) ?? ''}
                    onChange={(event) =>
                      updateField('prompt', event.target.value)
                    }
                  />
                </label>
                <label className="pixel-label">
                  Temperature
                  <input
                    className="pixel-input"
                    type="number"
                    value={Number(nodeData.temperature ?? 0.7)}
                    onChange={(event) =>
                      updateField('temperature', Number(event.target.value))
                    }
                    min={0}
                    max={2}
                    step={0.1}
                  />
                </label>
              </>
            ) : null}
            {nodeType === 'OUTPUT' ? (
              <label className="pixel-label">
                Output Key
                <input
                  className="pixel-input"
                  value={(nodeData.output_key as string) ?? ''}
                  onChange={(event) =>
                    updateField('output_key', event.target.value)
                  }
                />
              </label>
            ) : null}
          </div>
        )}
      </div>

      <div>
        <div className="pixel-section-title">Run Input</div>
        <textarea
          className="pixel-textarea mt-3 min-h-[160px]"
          value={runInput}
          onChange={(event) => onChangeRunInput(event.target.value)}
        />
        <div className="mt-2 text-xs text-[var(--muted)]">
          JSON payload отправится в `executions`.
        </div>
      </div>
    </aside>
  )
}
