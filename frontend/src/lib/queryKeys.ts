// Centralized query keys so a mutation in one place (e.g. deleting a
// Telegram bot in Settings) invalidates the exact same cache entry read
// elsewhere (e.g. NodeFieldsForm's bot picker) — one source of truth per
// resource instead of each hook hand-rolling its own key shape.
export const queryKeys = {
  nodeCatalog: () => ['node-catalog'] as const,
  workflows: () => ['workflows'] as const,
  workflowTemplates: () => ['workflow-templates'] as const,
  llmProviders: () => ['llm-providers'] as const,
  llmProviderModels: (providerId: number) =>
    ['llm-providers', providerId, 'models'] as const,
  telegramBots: () => ['telegram-bots'] as const,
  emailAccounts: () => ['email-accounts'] as const,
  postgresConnections: () => ['postgres-connections'] as const,
  mcpServers: () => ['mcp-servers'] as const,
  mcpTools: (serverId: number) => ['mcp-servers', serverId, 'tools'] as const,
  vectorCollections: () => ['vector-collections'] as const,
  vectorDocuments: (collection: string) =>
    ['vector-collections', collection, 'documents'] as const,
  activityLog: (workflowId: number) =>
    ['executions', workflowId, 'activity-log'] as const,
}
