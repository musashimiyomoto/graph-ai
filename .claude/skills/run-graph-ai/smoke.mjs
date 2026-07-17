// Full-stack execution smoke test for Graph AI (no browser).
//
// Exercises the ENTIRE pipeline against the running stack: register/login →
// create an Ollama provider → build an Input→LLM→Output graph → queue an
// execution → poll until the ARQ worker + Ollama produce output. Asserts the
// run reaches `success` with non-empty text, else exits non-zero.
//
// Requires the full stack incl. ollama + worker:
//   docker compose up -d --build          # everything, or at least: postgres redis qdrant backend frontend ollama worker
//   docker compose exec -T ollama ollama list   # confirm qwen2.5:0.5b is pulled
//
// Usage (from this skill dir):
//   node smoke.mjs
//   API=http://localhost:5000 MODEL=qwen2.5:0.5b node smoke.mjs

const API = process.env.API ?? 'http://localhost:5000'
const MODEL = process.env.MODEL ?? 'qwen2.5:0.5b'
const OLLAMA_URL = process.env.OLLAMA_URL ?? 'http://ollama:11434' // reachable from the backend container
const stamp = String(process.pid)
const email = process.env.EMAIL ?? `smoke+${stamp}@graph.ai`
const password = 'pw12345678'

let token = null
async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  const json = text ? JSON.parse(text) : null
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status} ${text}`)
  return json
}

async function main() {
  console.log(`→ register/login ${email}`)
  await api('/auth/register', { method: 'POST', body: { email, password } }).catch(() => {})
  token = (await api('/auth/login', { method: 'POST', body: { email, password } })).access_token

  console.log('→ create Ollama provider')
  const prov = await api('/llm-providers', {
    method: 'POST',
    body: { name: 'Local Ollama', type: 'ollama', base_url: OLLAMA_URL, config: {} },
  })

  console.log('→ create workflow + Input→LLM→Output graph')
  const wf = await api('/workflows', { method: 'POST', body: { name: `Smoke ${stamp}` } })
  const mk = (type, data, x) =>
    api('/nodes', { method: 'POST', body: { workflow_id: wf.id, type, data, position_x: x, position_y: 100 } })
  const input = await mk('input', { label: 'In', format: 'txt' }, 100)
  const llm = await mk('llm', { label: 'LLM', llm_provider_id: prov.id, model: MODEL, system_prompt: 'You are concise.' }, 400)
  const output = await mk('output', { label: 'Out', format: 'txt' }, 700)
  const edge = (s, t) =>
    api('/edges', { method: 'POST', body: { workflow_id: wf.id, source_node_id: s, target_node_id: t } })
  await edge(input.id, llm.id)
  await edge(llm.id, output.id)

  console.log('→ queue execution')
  const exec = await api('/executions', {
    method: 'POST',
    body: { workflow_id: wf.id, input_data: { value: 'Say hello in 3 words.' } },
  })

  console.log('→ poll for the worker + Ollama to finish')
  let last = null
  for (let i = 0; i < 60; i++) {
    // Tolerate transient fetch blips while the worker holds the event loop.
    const list = await api(`/executions?workflow_id=${wf.id}`).catch((e) => {
      console.log(`  [${i}] poll retry (${e.message})`)
      return null
    })
    if (!list) { await new Promise((r) => setTimeout(r, 2000)); continue }
    last = list.find((e) => e.id === exec.id)
    const out = last?.output_data?.value
    console.log(`  [${i}] status=${last?.status} output=${JSON.stringify(out ?? null)}`)
    if (last?.status === 'success') {
      if (!out) throw new Error('execution succeeded but output is empty')
      console.log(`\n✓ SMOKE PASSED — LLM output: ${JSON.stringify(out)}`)
      return
    }
    if (last?.status === 'failed') throw new Error(`execution failed: ${last.error}`)
    await new Promise((r) => setTimeout(r, 2000))
  }
  throw new Error(`execution did not finish; last status=${last?.status}`)
}

main().catch((err) => {
  console.error(`✗ SMOKE FAILED: ${err.message}`)
  process.exit(1)
})
