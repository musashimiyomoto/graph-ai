import { useMemo } from 'react'

import { useEmailAccounts } from '../hooks/useEmailAccounts'
import { useLlmProviders } from '../hooks/useLlmProviders'
import { useProviderModels } from '../hooks/useProviderModels'
import { useTelegramBots } from '../hooks/useTelegramBots'
import { useVectorCollections } from '../hooks/useVectorCollections'
import type {
  EmailAccount,
  LlmModel,
  LlmProvider,
  NodeCatalogField,
  TelegramBot,
  VectorCollection,
} from '../lib/types'
import { matchesVisibility } from '../lib/validation'
import { NumberInput } from './NumberInput'
import { VectorCollectionInput } from './VectorCollectionInput'

function TextField({
  value,
  placeholder,
  onChange,
}: {
  value: unknown
  placeholder: string | null
  onChange: (value: string) => void
}) {
  return (
    <input
      className="pixel-input"
      value={String(value ?? '')}
      placeholder={placeholder ?? ''}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

function TextAreaField({
  value,
  placeholder,
  onChange,
}: {
  value: unknown
  placeholder: string | null
  onChange: (value: string) => void
}) {
  return (
    <textarea
      className="pixel-textarea"
      value={String(value ?? '')}
      placeholder={placeholder ?? ''}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

function NumberField({
  field,
  value,
  onChange,
}: {
  field: NodeCatalogField
  value: unknown
  onChange: (value: number | string) => void
}) {
  // '' means the user explicitly cleared the field — kept as a string rather
  // than coerced to 0 (`Number('') === 0`) so a required field correctly
  // fails validation instead of silently saving as zero.
  const displayValue =
    value === '' ? '' : Number(value ?? field.default ?? field.validators.ge ?? 0)

  return (
    <NumberInput
      displayValue={displayValue}
      min={field.validators.ge}
      max={field.validators.le}
      step={field.ui.step ?? undefined}
      onChangeRaw={(raw) => onChange(raw === '' ? '' : Number(raw))}
    />
  )
}

function OptionalNumberField({
  field,
  value,
  onChange,
}: {
  field: NodeCatalogField
  value: unknown
  onChange: (value: number | null) => void
}) {
  const displayValue =
    value === null || value === undefined || value === '' ? '' : Number(value)

  return (
    <NumberInput
      displayValue={displayValue}
      placeholder="default"
      min={field.validators.ge}
      max={field.validators.le}
      step={field.ui.step ?? undefined}
      onChangeRaw={(raw) => onChange(raw === '' ? null : Number(raw))}
    />
  )
}

function SelectField({
  value,
  options,
  onChange,
}: {
  value: unknown
  options: string[]
  onChange: (value: string) => void
}) {
  return (
    <select
      className="pixel-input"
      value={String(value ?? options[0] ?? '')}
      onChange={(event) => onChange(event.target.value)}
    >
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  )
}

function ProviderField({
  providers,
  value,
  onChange,
}: {
  providers: LlmProvider[]
  value: unknown
  onChange: (value: number) => void
}) {
  return (
    <select
      className="pixel-input"
      value={String(value ?? '')}
      onChange={(event) => onChange(Number(event.target.value))}
    >
      <option value="">-- select provider --</option>
      {providers.map((provider) => (
        <option key={provider.id} value={provider.id}>
          {provider.name}
        </option>
      ))}
    </select>
  )
}

function ModelField({
  models,
  value,
  onChange,
}: {
  models: LlmModel[]
  value: unknown
  onChange: (value: string) => void
}) {
  return (
    <select
      className="pixel-input"
      value={String(value ?? '')}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">-- select model --</option>
      {models.map((model) => (
        <option key={model.name} value={model.name}>
          {model.name}
        </option>
      ))}
    </select>
  )
}

function TelegramBotField({
  bots,
  value,
  onChange,
}: {
  bots: TelegramBot[]
  value: unknown
  onChange: (value: number) => void
}) {
  return (
    <select
      className="pixel-input"
      value={String(value ?? '')}
      onChange={(event) => onChange(Number(event.target.value))}
    >
      <option value="">-- select bot --</option>
      {bots.map((bot) => (
        <option key={bot.id} value={bot.id}>
          {bot.name}
        </option>
      ))}
    </select>
  )
}

function EmailAccountField({
  accounts,
  value,
  onChange,
}: {
  accounts: EmailAccount[]
  value: unknown
  onChange: (value: number) => void
}) {
  return (
    <select
      className="pixel-input"
      value={String(value ?? '')}
      onChange={(event) => onChange(Number(event.target.value))}
    >
      <option value="">-- select account --</option>
      {accounts.map((account) => (
        <option key={account.id} value={account.id}>
          {account.name} ({account.email_address})
        </option>
      ))}
    </select>
  )
}

function VectorCollectionField({
  collections,
  value,
  placeholder,
  onChange,
}: {
  collections: VectorCollection[]
  value: unknown
  placeholder: string | null
  onChange: (value: string) => void
}) {
  return (
    <VectorCollectionInput
      collections={collections}
      value={String(value ?? '')}
      placeholder={placeholder}
      onChange={onChange}
    />
  )
}

interface NodeFieldsFormProps {
  fields: NodeCatalogField[]
  data: Record<string, unknown>
  errors: Record<string, string>
  onFieldChange: (name: string, nextData: Record<string, unknown>) => void
}

export function NodeFieldsForm({ fields, data, errors, onFieldChange }: NodeFieldsFormProps) {
  const hasProviderDatasource = fields.some(
    (field) => field.datasource?.kind === 'llm_provider',
  )
  const hasModelDatasource = fields.some((field) => field.datasource?.kind === 'llm_model')
  const hasTelegramBotDatasource = fields.some(
    (field) => field.datasource?.kind === 'telegram_bot',
  )
  const hasEmailAccountDatasource = fields.some(
    (field) => field.datasource?.kind === 'email_account',
  )
  const hasVectorCollectionDatasource = fields.some(
    (field) => field.datasource?.kind === 'vector_collection',
  )

  const selectedProviderRaw = Number(data['llm_provider_id'] ?? 0)
  const selectedProviderId =
    Number.isInteger(selectedProviderRaw) && selectedProviderRaw > 0
      ? selectedProviderRaw
      : null

  const { providers, loading: providersLoading } = useLlmProviders({
    enabled: hasProviderDatasource,
  })
  const { models, loading: modelsLoading } = useProviderModels({
    providerId: selectedProviderId,
    enabled: hasModelDatasource,
  })
  const { bots, loading: botsLoading } = useTelegramBots({
    enabled: hasTelegramBotDatasource,
  })
  const { accounts, loading: accountsLoading } = useEmailAccounts({
    enabled: hasEmailAccountDatasource,
  })
  const { collections } = useVectorCollections({
    enabled: hasVectorCollectionDatasource,
  })

  // A saved id/name that no longer matches anything in its data source (the
  // provider/model/bot was deleted after the node was configured) would
  // otherwise just render as a blank dropdown with no explanation, silently
  // keeping the dead reference in the node's config.
  function referenceWarning(field: NodeCatalogField): string | null {
    const value = data[field.name]
    if (!value) {
      return null
    }
    if (field.ui.widget === 'provider' && !providersLoading) {
      return providers.some((provider) => provider.id === Number(value))
        ? null
        : 'Selected provider no longer exists.'
    }
    if (field.ui.widget === 'model' && !modelsLoading) {
      return models.some((model) => model.name === value)
        ? null
        : 'Selected model is no longer available.'
    }
    if (field.ui.widget === 'telegram_bot' && !botsLoading) {
      return bots.some((bot) => bot.id === Number(value)) ? null : 'Selected bot no longer exists.'
    }
    if (field.ui.widget === 'email_account' && !accountsLoading) {
      return accounts.some((account) => account.id === Number(value))
        ? null
        : 'Selected email account no longer exists.'
    }
    return null
  }

  const visibleFields = useMemo(
    () =>
      fields.filter((field) => {
        // Declarative conditional visibility: a field with visible_when is
        // only shown once its controlling sibling field holds the required
        // value. Driven entirely by the catalog, so a future format-gated
        // field needs no new frontend branch — just a visible_when in its
        // NodeFieldSpec.
        if (!field.visible_when) {
          return true
        }
        return matchesVisibility(field.visible_when, data[field.visible_when.field])
      }),
    [fields, data],
  )

  function updateField(name: string, value: string | number | null) {
    const next = { ...data, [name]: value }
    // Generic clear-on-hide: any sibling field whose visibility depends on
    // this one gets reset once it's no longer visible, so a hidden field's
    // stale value (e.g. a bot ID left over from a different format) never
    // gets saved silently alongside the new value. Also resets any field
    // whose *data source* depends on this one (e.g. model options depend on
    // the selected provider), so a stale model never survives a provider
    // change.
    for (const dependent of fields) {
      if (
        dependent.visible_when?.field === name &&
        !matchesVisibility(dependent.visible_when, value)
      ) {
        next[dependent.name] = null
      }
      if (dependent.datasource?.depends_on === name) {
        next[dependent.name] = null
      }
    }
    onFieldChange(name, next)
  }

  function renderField(field: NodeCatalogField) {
    const value = data[field.name]

    if (field.ui.widget === 'provider') {
      return (
        <ProviderField
          providers={providers}
          value={value}
          onChange={(providerId) => updateField(field.name, providerId)}
        />
      )
    }

    if (field.ui.widget === 'model') {
      return (
        <ModelField
          models={models}
          value={value}
          onChange={(model) => updateField(field.name, model)}
        />
      )
    }

    if (field.ui.widget === 'telegram_bot') {
      return (
        <TelegramBotField
          bots={bots}
          value={value}
          onChange={(botId) => updateField(field.name, botId)}
        />
      )
    }

    if (field.ui.widget === 'email_account') {
      return (
        <EmailAccountField
          accounts={accounts}
          value={value}
          onChange={(accountId) => updateField(field.name, accountId)}
        />
      )
    }

    if (field.ui.widget === 'vector_collection') {
      return (
        <VectorCollectionField
          collections={collections}
          value={value}
          placeholder={field.ui.placeholder}
          onChange={(collection) => updateField(field.name, collection)}
        />
      )
    }

    if (field.ui.widget === 'select') {
      return (
        <SelectField
          value={value}
          options={field.validators.select ?? []}
          onChange={(selected) => updateField(field.name, selected)}
        />
      )
    }

    if (field.ui.widget === 'number') {
      return (
        <NumberField
          field={field}
          value={value}
          onChange={(numberValue) => updateField(field.name, numberValue)}
        />
      )
    }

    if (field.ui.widget === 'optional_number') {
      return (
        <OptionalNumberField
          field={field}
          value={value}
          onChange={(numberValue) => updateField(field.name, numberValue)}
        />
      )
    }

    if (field.ui.widget === 'textarea') {
      return (
        <TextAreaField
          value={value}
          placeholder={field.ui.placeholder}
          onChange={(text) => updateField(field.name, text)}
        />
      )
    }

    return (
      <TextField
        value={value}
        placeholder={field.ui.placeholder}
        onChange={(text) => updateField(field.name, text)}
      />
    )
  }

  return (
    <>
      {visibleFields.map((field) => {
        const warning = referenceWarning(field)
        return (
          <label key={field.name} className="pixel-label">
            {field.ui.label}
            {renderField(field)}
            {errors[field.name] ? (
              <span className="text-xs text-[var(--danger)]">{errors[field.name]}</span>
            ) : warning ? (
              <span className="text-xs text-[var(--accent-2)]">{warning}</span>
            ) : field.ui.help ? (
              <span className="text-xs text-[var(--muted)]">{field.ui.help}</span>
            ) : null}
          </label>
        )
      })}
    </>
  )
}
