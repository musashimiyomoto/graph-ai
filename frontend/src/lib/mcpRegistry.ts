import type { MCPRegistryServer } from './types'

const VARIABLE_PATTERN = /\{([A-Za-z][A-Za-z0-9_]*)\}/g

function substitute(
  template: string,
  values: Record<string, string>,
  encode: boolean,
): string {
  return template.replace(VARIABLE_PATTERN, (_match, key: string) => {
    const value = values[key] ?? ''
    return encode ? encodeURIComponent(value) : value
  })
}

export function resolveRegistryConfiguration(
  server: MCPRegistryServer,
  values: Record<string, string>,
): { url: string; headers: Record<string, string> } {
  return {
    url: substitute(server.url_template, values, true),
    headers: Object.fromEntries(
      Object.entries(server.header_templates).map(([name, template]) => [
        name,
        substitute(template, values, false),
      ]),
    ),
  }
}
