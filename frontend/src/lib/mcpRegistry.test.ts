import { describe, expect, it } from 'vitest'

import { resolveRegistryConfiguration } from './mcpRegistry'
import type { MCPRegistryServer } from './types'

describe('MCP Registry configuration', () => {
  it('resolves URL variables and secret header templates', () => {
    const server: MCPRegistryServer = {
      registry_name: 'example/tools',
      name: 'tools',
      description: null,
      version: '1.0.0',
      url_template: 'https://example.com/{workspace}/mcp',
      header_templates: { Authorization: 'Bearer {token}' },
      inputs: [],
      repository_url: null,
    }

    expect(
      resolveRegistryConfiguration(server, {
        workspace: 'my team',
        token: 'secret',
      }),
    ).toEqual({
      url: 'https://example.com/my%20team/mcp',
      headers: { Authorization: 'Bearer secret' },
    })
  })
})
