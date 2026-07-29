import { getSettingsSectionLabel } from '../lib/settingsSections'
import type { SettingsSectionId, WorkflowTemplate } from '../lib/types'

interface TemplateSetupPanelProps {
  template: WorkflowTemplate
  onOpenSettings: (sectionId: SettingsSectionId) => void
  onDismiss: () => void
}

export function TemplateSetupPanel({
  template,
  onOpenSettings,
  onDismiss,
}: TemplateSetupPanelProps) {
  return (
    <aside className="pixel-panel pixel-scroll flex h-full flex-col overflow-y-auto">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="pixel-section-title">Finish setup</div>
          <p className="mt-2 text-sm text-[var(--text)]">{template.name}</p>
        </div>
        <button
          type="button"
          className="pixel-icon"
          aria-label="Dismiss template setup guide"
          onClick={onDismiss}
        >
          ✕
        </button>
      </div>

      <p className="mt-4 text-xs leading-relaxed text-[var(--muted)]">
        The graph is ready. Complete these steps before the first run.
      </p>

      <ol className="mt-5 space-y-3">
        {template.setup_steps.map((step, index) => (
          <li key={step} className="pixel-card items-start p-3">
            <span className="text-[var(--accent)]">{index + 1}.</span>
            <span className="text-xs leading-relaxed text-[var(--muted)]">
              {step}
            </span>
          </li>
        ))}
      </ol>

      {template.settings_sections.length > 0 ? (
        <div className="mt-5 flex flex-col gap-2">
          {template.settings_sections.map((sectionId) => (
            <button
              key={sectionId}
              type="button"
              className="pixel-button ghost small"
              onClick={() => onOpenSettings(sectionId)}
            >
              Open {getSettingsSectionLabel(sectionId)}
            </button>
          ))}
        </div>
      ) : null}

      <div className="mt-5 border-t border-white/10 pt-4 text-xs leading-relaxed text-[var(--muted)]">
        After creating the resource, return to Editor, select the node named above,
        and choose the resource in Inspector. Changes save automatically.
      </div>
    </aside>
  )
}
