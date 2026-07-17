// Browser driver for the Graph AI web app (frontend :3000 + backend :5000).
//
// Drives the real running stack with a headless Playwright Chromium:
// registers/logs in a user through the UI and screenshots the auth screen
// and the workflow-builder canvas. Screenshots land in ./shots/.
//
// Usage (from this skill dir, after `npm install && npx playwright install chromium`):
//   node driver.mjs                      # default flow, demo@graph.ai
//   node driver.mjs --email a@b.co --password secret123
//   BASE=http://localhost:3000 node driver.mjs
//
// Exit code is non-zero if any step fails, so it doubles as a smoke test.

import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const SHOTS = join(HERE, 'shots')
mkdirSync(SHOTS, { recursive: true })

const BASE = process.env.BASE ?? 'http://localhost:3000'

function arg(flag, fallback) {
  const i = process.argv.indexOf(flag)
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback
}

// A fresh-ish email each run avoids "already registered" collisions while
// staying deterministic within a run (no Math.random needed).
const stamp = process.env.STAMP ?? String(process.pid)
const email = arg('--email', `demo+${stamp}@graph.ai`)
const password = arg('--password', 'demopass123')

async function shot(page, name) {
  const path = join(SHOTS, `${name}.png`)
  await page.screenshot({ path, fullPage: false })
  console.log(`  📸 ${path}`)
}

let pageRef = null

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  pageRef = page
  page.on('console', (m) => {
    if (m.type() === 'error') console.log(`  [console.error] ${m.text()}`)
  })

  console.log(`→ open ${BASE}`)
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: /pixel flow studio/i }).waitFor()
  await shot(page, '01-auth')

  // Register the user (Register tab). On success the app auto-logs-in
  // (handleRegister → handleLogin in useAuthSession).
  console.log(`→ register ${email}`)
  await page.getByRole('button', { name: 'Register', exact: true }).click()
  await page.getByPlaceholder('you@graph.ai').fill(email)
  await page.getByPlaceholder('••••••••').fill(password)
  await page.getByRole('button', { name: 'Create Account' }).click()

  // Post-auth the builder shell renders. The email is NOT in the top bar
  // (it lives inside the closed Profile dropdown), so wait on the "Settings"
  // top-bar button, which only exists once authenticated.
  console.log('→ wait for workflow builder')
  await page.getByRole('button', { name: 'Settings', exact: true }).waitFor({ timeout: 15000 })
  await page.waitForTimeout(500)
  await shot(page, '02-builder')

  // Create a workflow: fill the "New workflow" input in the sidebar + click Add.
  console.log('→ create a workflow')
  await page.getByPlaceholder('New workflow').fill('Demo Flow')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await page.getByText('Demo Flow').first().waitFor({ timeout: 10000 })
  await page.waitForTimeout(500)
  await shot(page, '03-workflow')

  if (process.argv.includes('--run')) {
    await runWorkflow(page)
  }

  console.log('✓ driver flow complete')
  await browser.close()
}

// Build an Input→LLM→Output graph via the app's own /api proxy (using the
// logged-in token), then drive the History → Chat panel to actually execute it
// against Ollama + the ARQ worker, and screenshot the streamed LLM response.
// Requires the full stack: ollama (model pulled) + worker running.
async function runWorkflow(page) {
  const model = process.env.MODEL ?? 'qwen2.5:0.5b'
  const ollamaUrl = process.env.OLLAMA_URL ?? 'http://ollama:11434'

  console.log('→ build Input→LLM→Output graph via /api')
  const wfName = `UI Run ${process.env.STAMP ?? process.pid}`
  // All requests run in the page so they reuse localStorage token + the /api proxy.
  const built = await page.evaluate(
    async ({ wfName, model, ollamaUrl }) => {
      const token = localStorage.getItem('graph_ai_token')
      const call = async (path, body) => {
        const res = await fetch(`/api${path}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify(body),
        })
        if (!res.ok) throw new Error(`${path} → ${res.status} ${await res.text()}`)
        return res.json()
      }
      const prov = await call('/llm-providers', { name: 'Local Ollama', type: 'ollama', base_url: ollamaUrl, config: {} })
      const wf = await call('/workflows', { name: wfName })
      const node = (type, data, x) => call('/nodes', { workflow_id: wf.id, type, data, position_x: x, position_y: 120 })
      const input = await node('input', { label: 'In', format: 'txt' }, 80)
      const llm = await node('llm', { label: 'LLM', llm_provider_id: prov.id, model, system_prompt: 'You are concise.' }, 380)
      const output = await node('output', { label: 'Out', format: 'txt' }, 680)
      await call('/edges', { workflow_id: wf.id, source_node_id: input.id, target_node_id: llm.id })
      await call('/edges', { workflow_id: wf.id, source_node_id: llm.id, target_node_id: output.id })
      return { wfId: wf.id, wfName }
    },
    { wfName, model, ollamaUrl },
  )

  console.log('→ reload and select the workflow')
  await page.reload({ waitUntil: 'networkidle' })
  await page.getByRole('button', { name: built.wfName, exact: true }).click()
  // Wait for the canvas to render the three nodes (ReactFlow node labels).
  await page.getByText('LLM', { exact: false }).first().waitFor({ timeout: 10000 })
  await page.waitForTimeout(800)
  await shot(page, '04-graph')

  console.log('→ open History and run the flow')
  await page.getByRole('button', { name: 'History', exact: true }).click()
  const box = page.locator('textarea').first()
  await box.waitFor({ timeout: 10000 })
  await box.fill('Say hello in 3 words.')
  await page.getByRole('button', { name: /^Send$/ }).click()

  // The response bubble fills once the worker + Ollama finish (CPU: give it time).
  console.log('→ wait for the LLM response')
  await page.getByText('success', { exact: false }).first().waitFor({ timeout: 90000 })
  await page.waitForTimeout(1000)
  await shot(page, '05-run')
  console.log('✓ workflow executed through the UI')
}

main().catch(async (err) => {
  console.error('✗ driver failed:', err.message)
  if (pageRef) await shot(pageRef, 'error').catch(() => {})
  process.exit(1)
})
