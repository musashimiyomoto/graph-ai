import { useEffect, useMemo, useState } from 'react'

import { useWorkflowTemplates } from '../hooks/useWorkflowTemplates'
import type { WorkflowTemplate } from '../lib/types'

interface NewFromTemplateDialogProps {
  onCancel: () => void
  onConfirm: (templateKey: string, name: string) => Promise<void>
}

const ALL_CATEGORIES = 'All'

function filterTemplates(
  templates: WorkflowTemplate[],
  query: string,
  category: string,
): WorkflowTemplate[] {
  const normalizedQuery = query.trim().toLowerCase()
  return templates.filter((template) => {
    const matchesCategory =
      category === ALL_CATEGORIES || template.category === category
    const searchable = [
      template.name,
      template.description,
      template.category,
      ...template.setup_steps,
    ]
      .join(' ')
      .toLowerCase()
    return matchesCategory && searchable.includes(normalizedQuery)
  })
}

export function NewFromTemplateDialog({
  onCancel,
  onConfirm,
}: NewFromTemplateDialogProps) {
  const { templates, loading } = useWorkflowTemplates()
  const [creatingKey, setCreatingKey] = useState<string | null>(null)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [workflowName, setWorkflowName] = useState('')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState(ALL_CATEGORIES)

  const categories = useMemo(
    () => [
      ALL_CATEGORIES,
      ...Array.from(new Set(templates.map((template) => template.category))).sort(),
    ],
    [templates],
  )
  const filteredTemplates = useMemo(
    () => filterTemplates(templates, query, category),
    [category, query, templates],
  )
  const selectedTemplate =
    templates.find((template) => template.key === selectedKey) ?? null

  useEffect(() => {
    const firstTemplate = templates[0]
    if (selectedKey === null && firstTemplate) {
      setSelectedKey(firstTemplate.key)
      setWorkflowName(firstTemplate.name)
    }
  }, [selectedKey, templates])

  function selectTemplate(template: WorkflowTemplate): void {
    setSelectedKey(template.key)
    setWorkflowName(template.name)
  }

  function handleQueryChange(value: string): void {
    setQuery(value)
    const matches = filterTemplates(templates, value, category)
    if (!matches.some((template) => template.key === selectedKey) && matches[0]) {
      selectTemplate(matches[0])
    }
  }

  function handleCategoryChange(value: string): void {
    setCategory(value)
    const matches = filterTemplates(templates, query, value)
    if (!matches.some((template) => template.key === selectedKey) && matches[0]) {
      selectTemplate(matches[0])
    }
  }

  async function handleCreate(): Promise<void> {
    const name = workflowName.trim()
    if (!selectedTemplate || !name) {
      return
    }
    setCreatingKey(selectedTemplate.key)
    try {
      await onConfirm(selectedTemplate.key, name)
    } finally {
      setCreatingKey(null)
    }
  }

  return (
    <section className="pixel-panel pixel-scroll h-full overflow-y-auto p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="pixel-section-title">Template Library</div>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Start with a ready-made graph, then adapt it to your workflow.
          </p>
        </div>
        <button
          type="button"
          className="pixel-icon"
          aria-label="Close template library"
          disabled={creatingKey !== null}
          onClick={onCancel}
        >
          ✕
        </button>
      </div>

      <div className="mt-5 flex flex-col gap-3">
        <input
          type="search"
          className="pixel-input"
          aria-label="Search templates"
          placeholder="Search templates..."
          value={query}
          disabled={creatingKey !== null}
          onChange={(event) => handleQueryChange(event.target.value)}
        />
        <div className="flex flex-wrap gap-2" aria-label="Template categories">
          {categories.map((item) => (
            <button
              key={item}
              type="button"
              className={`pixel-button ghost small ${
                category === item ? 'border-[var(--accent)] text-[var(--accent)]' : ''
              }`}
              aria-pressed={category === item}
              disabled={creatingKey !== null}
              onClick={() => handleCategoryChange(item)}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)]">
        {loading ? (
          <div className="pixel-card min-h-40 items-center justify-center text-sm text-[var(--muted)] md:col-span-2">
            Loading templates...
          </div>
        ) : templates.length === 0 ? (
          <div className="pixel-card min-h-40 items-center justify-center text-sm text-[var(--muted)] md:col-span-2">
            No templates available.
          </div>
        ) : (
          <>
            <div className="flex max-h-[28rem] flex-col gap-2 overflow-y-auto pr-1">
              <div className="mb-1 text-xs text-[var(--muted)]">
                {filteredTemplates.length}{' '}
                {filteredTemplates.length === 1 ? 'template' : 'templates'}
              </div>
              {filteredTemplates.length === 0 ? (
                <div className="pixel-card min-h-32 flex-col items-start justify-center">
                  <div className="text-sm">No matching templates</div>
                  <div className="mt-1 text-xs text-[var(--muted)]">
                    Try another search or category.
                  </div>
                </div>
              ) : (
                filteredTemplates.map((template) => (
                  <button
                    key={template.key}
                    type="button"
                    className={`pixel-card w-full flex-col items-start p-3 text-left ${
                      selectedTemplate?.key === template.key ? 'is-active' : ''
                    }`}
                    aria-pressed={selectedTemplate?.key === template.key}
                    disabled={creatingKey !== null}
                    onClick={() => selectTemplate(template)}
                  >
                    <div className="flex w-full items-center justify-between gap-3">
                      <span className="text-sm text-[var(--text)]">{template.name}</span>
                      <span className="pixel-pill shrink-0">{template.node_count} nodes</span>
                    </div>
                    <span className="text-xs text-[var(--accent-2)]">
                      {template.category}
                    </span>
                    <span className="line-clamp-2 text-xs text-[var(--muted)]">
                      {template.description}
                    </span>
                  </button>
                ))
              )}
            </div>

            <div className="border-2 border-white/10 bg-white/[0.02] p-4">
              {selectedTemplate ? (
                <div className="flex h-full flex-col">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="pixel-pill text-[var(--accent-2)]">
                      {selectedTemplate.category}
                    </span>
                    <span className="text-xs text-[var(--muted)]">
                      {selectedTemplate.node_count} nodes
                    </span>
                  </div>
                  <h2 className="mt-3 text-xl text-[var(--text)]">
                    {selectedTemplate.name}
                  </h2>
                  <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
                    {selectedTemplate.description}
                  </p>

                  <div className="mt-5">
                    <div className="text-xs uppercase tracking-wider text-[var(--accent-2)]">
                      Before the first run
                    </div>
                    {selectedTemplate.setup_steps.length > 0 ? (
                      <ul className="mt-2 space-y-2 text-sm text-[var(--muted)]">
                        {selectedTemplate.setup_steps.map((step) => (
                          <li key={step} className="flex gap-2">
                            <span className="text-[var(--accent)]">›</span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="mt-2 text-sm text-[var(--accent)]">
                        Ready to run — no connections required.
                      </div>
                    )}
                  </div>

                  <label className="mt-6 block text-xs text-[var(--muted)]">
                    Workflow name
                    <input
                      className="pixel-input mt-2"
                      value={workflowName}
                      maxLength={200}
                      disabled={creatingKey !== null}
                      onChange={(event) => setWorkflowName(event.target.value)}
                    />
                  </label>

                  <div className="mt-auto flex justify-end gap-2 pt-6">
                    <button
                      type="button"
                      className="pixel-button ghost"
                      onClick={onCancel}
                      disabled={creatingKey !== null}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="pixel-button"
                      disabled={creatingKey !== null || workflowName.trim().length === 0}
                      onClick={() => void handleCreate()}
                    >
                      {creatingKey === selectedTemplate.key
                        ? 'Creating...'
                        : 'Create workflow'}
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </>
        )}
      </div>
    </section>
  )
}
