import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Edge, Node as FlowNode } from 'reactflow'

import { AuthScreen } from './components/AuthScreen'
import { AppShell } from './components/AppShell'
import { GraphCanvas } from './components/GraphCanvas'
import { InspectorPanel } from './components/InspectorPanel'
import { WorkflowSidebar } from './components/WorkflowSidebar'
import {
  createEdge,
  createExecution,
  createNode,
  createWorkflow,
  deleteEdge,
  deleteWorkflow,
  getEdges,
  getMe,
  getNodes,
  getWorkflows,
  login,
  register,
  setToken,
  updateNode,
  updateWorkflow,
} from './lib/api'
import type {
  ApiError,
  Execution,
  NodeCreatePayload,
  NodeType,
  Workflow,
} from './lib/types'

const TOKEN_KEY = 'graph_ai_token'

export function App() {
  const [token, setTokenState] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY),
  )
  const [email, setEmail] = useState<string>('')
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [activeWorkflowId, setActiveWorkflowId] = useState<number | null>(null)
  const [nodes, setNodes] = useState<FlowNode[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [runInput, setRunInput] = useState<string>('{}')
  const [lastExecution, setLastExecution] = useState<Execution | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)

  const activeWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === activeWorkflowId) ?? null,
    [activeWorkflowId, workflows],
  )

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  )

  const handleLogout = useCallback((): void => {
    localStorage.removeItem(TOKEN_KEY)
    setTokenState(null)
    setEmail('')
    setWorkflows([])
    setActiveWorkflowId(null)
    setNodes([])
    setEdges([])
    setSelectedNodeId(null)
    setLastExecution(null)
    setError(null)
  }, [])

  const handleError = useCallback(
    (err: ApiError): void => {
      if (err.status === 401) {
        handleLogout()
        return
      }
      setError(err.message)
    },
    [handleLogout],
  )

  useEffect(() => {
    setToken(token)
  }, [token])

  useEffect(() => {
    if (!token) {
      return
    }

    setLoading(true)
    void getMe()
      .then((profile) => setEmail(profile.email))
      .catch((err: ApiError) => handleError(err))
      .finally(() => setLoading(false))
  }, [handleError, token])

  useEffect(() => {
    if (!token) {
      return
    }

    setLoading(true)
    void getWorkflows()
      .then((items) => {
        setWorkflows(items)
        setActiveWorkflowId((prev) => prev ?? items[0]?.id ?? null)
      })
      .catch((err: ApiError) => handleError(err))
      .finally(() => setLoading(false))
  }, [handleError, token])

  useEffect(() => {
    if (!token || !activeWorkflowId) {
      setNodes([])
      setEdges([])
      return
    }

    setLoading(true)
    Promise.all([
      getNodes(activeWorkflowId),
      getEdges(activeWorkflowId),
    ]).then(([nodeItems, edgeItems]) => {
      setNodes(
        nodeItems.map((node) => ({
          id: String(node.id),
          type: 'default',
          position: { x: node.position_x, y: node.position_y },
          data: {
            ...node.data,
            label: node.data?.label ?? `${node.type} node`,
            nodeType: node.type,
          },
        })),
      )
      setEdges(
        edgeItems.map((edge) => ({
          id: String(edge.id),
          source: String(edge.source_node_id),
          target: String(edge.target_node_id),
        })),
      )
    })
      .catch((err: ApiError) => handleError(err))
      .finally(() => setLoading(false))
  }, [activeWorkflowId, handleError, token])

  async function handleLogin(emailValue: string, password: string): Promise<void> {
    setLoading(true)
    try {
      const response = await login(emailValue, password)
      localStorage.setItem(TOKEN_KEY, response.access_token)
      setTokenState(response.access_token)
      setError(null)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister(
    emailValue: string,
    password: string,
  ): Promise<void> {
    setLoading(true)
    try {
      await register(emailValue, password)
      await handleLogin(emailValue, password)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateWorkflow(name: string): Promise<void> {
    if (!name.trim()) {
      return
    }
    setLoading(true)
    try {
      const created = await createWorkflow(name.trim())
      setWorkflows((prev) => [created, ...prev])
      setActiveWorkflowId(created.id)
      setError(null)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  async function handleRenameWorkflow(
    workflowId: number,
    name: string,
  ): Promise<void> {
    setLoading(true)
    try {
      const updated = await updateWorkflow(workflowId, name)
      setWorkflows((prev) =>
        prev.map((workflow) =>
          workflow.id === workflowId ? updated : workflow,
        ),
      )
      setError(null)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  async function handleDeleteWorkflow(workflowId: number): Promise<void> {
    setLoading(true)
    try {
      await deleteWorkflow(workflowId)
      setWorkflows((prev) => {
        const next = prev.filter((workflow) => workflow.id !== workflowId)
        if (activeWorkflowId === workflowId) {
          setActiveWorkflowId(next[0]?.id ?? null)
        }
        return next
      })
      setError(null)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  async function handleAddNode(type: NodeType): Promise<void> {
    if (!activeWorkflowId) {
      return
    }
    setLoading(true)
    try {
      const payload: NodeCreatePayload = {
        workflow_id: activeWorkflowId,
        type,
        data: { label: `${type} node` },
        position_x: 120 + nodes.length * 36,
        position_y: 120 + nodes.length * 36,
      }
      const created = await createNode(payload)
      setNodes((prev) => [
        ...prev,
        {
          id: String(created.id),
          type: 'default',
          position: { x: created.position_x, y: created.position_y },
          data: {
            ...created.data,
            label: created.data?.label ?? `${created.type} node`,
            nodeType: created.type,
          },
        },
      ])
      setSelectedNodeId(String(created.id))
      setError(null)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  async function handleUpdateNodeData(
    nodeId: string,
    data: Record<string, unknown>,
  ): Promise<void> {
    setLoading(true)
    try {
      const updated = await updateNode(Number(nodeId), { data })
      setNodes((prev) =>
        prev.map((node) =>
          node.id === nodeId
            ? {
                ...node,
                data: {
                  ...updated.data,
                  label: updated.data?.label ?? node.data?.label,
                  nodeType: updated.type,
                },
              }
            : node,
        ),
      )
      setError(null)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  async function handleMoveNode(nodeId: string, x: number, y: number): Promise<void> {
    try {
      await updateNode(Number(nodeId), { position_x: x, position_y: y })
    } catch (err) {
      handleError(err as ApiError)
    }
  }

  async function handleConnect(
    sourceId: string,
    targetId: string,
  ): Promise<void> {
    if (!activeWorkflowId) {
      return
    }
    setLoading(true)
    try {
      const created = await createEdge({
        workflow_id: activeWorkflowId,
        source_node_id: Number(sourceId),
        target_node_id: Number(targetId),
      })
      setEdges((prev) => [
        ...prev,
        {
          id: String(created.id),
          source: String(created.source_node_id),
          target: String(created.target_node_id),
        },
      ])
      setError(null)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  async function handleDeleteEdge(edgeId: string): Promise<void> {
    setLoading(true)
    try {
      await deleteEdge(Number(edgeId))
      setEdges((prev) => prev.filter((edge) => edge.id !== edgeId))
      setError(null)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  async function handleRun(): Promise<void> {
    if (!activeWorkflowId) {
      return
    }
    setLoading(true)
    try {
      const parsed = runInput.trim() ? (JSON.parse(runInput) as object) : null
      const execution = await createExecution(activeWorkflowId, parsed)
      setLastExecution(execution)
      setError(null)
    } catch (err) {
      handleError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <AuthScreen
        loading={loading}
        error={error}
        onLogin={handleLogin}
        onRegister={handleRegister}
      />
    )
  }

  return (
    <AppShell
      email={email}
      workflowName={activeWorkflow?.name ?? 'Untitled workflow'}
      executionStatus={lastExecution?.status ?? null}
      error={error}
      loading={loading}
      onRun={handleRun}
      onLogout={handleLogout}
    >
      <WorkflowSidebar
        workflows={workflows}
        activeWorkflowId={activeWorkflowId}
        onSelectWorkflow={setActiveWorkflowId}
        onCreateWorkflow={handleCreateWorkflow}
        onRenameWorkflow={handleRenameWorkflow}
        onDeleteWorkflow={handleDeleteWorkflow}
        onAddNode={handleAddNode}
      />
      <GraphCanvas
        nodes={nodes}
        edges={edges}
        selectedNodeId={selectedNodeId}
        onSelectNode={setSelectedNodeId}
        onMoveNode={handleMoveNode}
        onConnect={handleConnect}
        onDeleteEdge={handleDeleteEdge}
      />
      <InspectorPanel
        node={selectedNode}
        runInput={runInput}
        onChangeRunInput={setRunInput}
        onSaveNode={handleUpdateNodeData}
      />
    </AppShell>
  )
}
