import { useCallback, useMemo, useState } from 'react'

import { AppShell } from './components/AppShell'
import { AuthScreen } from './components/AuthScreen'
import { CreateNodeDialog } from './components/CreateNodeDialog'
import { GraphCanvas } from './components/GraphCanvas'
import { InspectorPanel } from './components/InspectorPanel'
import { WorkflowSidebar } from './components/WorkflowSidebar'
import { useAuthSession } from './hooks/useAuthSession'
import { useExecutions } from './hooks/useExecutions'
import { useGraphState } from './hooks/useGraphState'
import { useNodeCatalog } from './hooks/useNodeCatalog'
import { useWorkflowState } from './hooks/useWorkflowState'
import type { ApiError, NodeType } from './lib/types'

interface NodeCreateDraft {
  type: NodeType
  position: {
    x: number
    y: number
  }
}

export function App() {
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [nodeCreateDraft, setNodeCreateDraft] = useState<NodeCreateDraft | null>(null)

  const {
    token,
    email,
    handleError,
    handleLogin,
    handleRegister,
    handleLogout: logoutAuth,
    handleDeleteAccount: deleteAccountAuth,
  } = useAuthSession({
    setLoading,
    setError,
  })

  const {
    workflows,
    activeWorkflowId,
    setActiveWorkflowId,
    clearWorkflowState,
    handleCreateWorkflow,
    handleRenameWorkflow,
    handleDeleteWorkflow,
  } = useWorkflowState({
    token,
    setLoading,
    setError,
    handleError,
  })

  const {
    nodeCatalog,
    nodeCatalogByType,
  } = useNodeCatalog({
    handleError,
  })

  const {
    nodes,
    edges,
    selectedNode,
    clearGraphState,
    setSelectedNodeId,
    createNodeWithData,
    getInitialNodeData,
    handleDeleteNode,
    handleUpdateNodeData,
    handleNodesChange,
    handleMoveNode,
    handleConnect,
    handleDeleteEdge,
  } = useGraphState({
    token,
    activeWorkflowId,
    nodeCatalogByType,
    setLoading,
    setError,
    handleError,
  })

  const {
    executions,
    lastExecution,
    runInput,
    clearExecutions,
    handleRun,
  } = useExecutions({
    token,
    activeWorkflowId,
    setLoading,
    setError,
    handleError,
  })

  const activeWorkflow = workflows.find((workflow) => workflow.id === activeWorkflowId) ?? null
  const inputNodes = useMemo(
    () => nodes.filter((node) => node.type === 'input'),
    [nodes],
  )
  const outputNodes = useMemo(
    () => nodes.filter((node) => node.type === 'output'),
    [nodes],
  )
  const inputFormat = String(inputNodes[0]?.data?.format ?? 'txt')
  const runDisabledReason = useMemo((): string | null => {
    if (!activeWorkflowId) {
      return 'Select a workflow to run.'
    }
    if (inputNodes.length !== 1) {
      return 'Workflow must contain exactly one input node.'
    }
    if (outputNodes.length !== 1) {
      return 'Workflow must contain exactly one output node.'
    }
    if (inputFormat !== 'txt') {
      return `Unsupported input format: ${inputFormat}.`
    }
    return null
  }, [activeWorkflowId, inputFormat, inputNodes.length, outputNodes.length])
  const runEnabled = runDisabledReason === null

  const handleLogout = useCallback(() => {
    clearExecutions()
    clearGraphState()
    clearWorkflowState()
    setNodeCreateDraft(null)
    logoutAuth()
  }, [clearExecutions, clearGraphState, clearWorkflowState, logoutAuth])

  const handleDeleteAccount = useCallback(async () => {
    await deleteAccountAuth()
    clearExecutions()
    clearGraphState()
    clearWorkflowState()
    setNodeCreateDraft(null)
  }, [clearExecutions, clearGraphState, clearWorkflowState, deleteAccountAuth])

  const requestCreateNode = useCallback(
    (type: NodeType, position: { x: number; y: number }) => {
      if (!activeWorkflowId) {
        return
      }
      setNodeCreateDraft({ type, position })
    },
    [activeWorkflowId],
  )

  const handleAddNode = useCallback(
    (type: NodeType) => {
      requestCreateNode(type, {
        x: 120 + nodes.length * 36,
        y: 120 + nodes.length * 36,
      })
    },
    [nodes.length, requestCreateNode],
  )

  const handleDropNode = useCallback(
    (type: string, position: { x: number; y: number }) => {
      requestCreateNode(type, position)
    },
    [requestCreateNode],
  )

  const createNodeSpec = nodeCreateDraft
    ? nodeCatalogByType[nodeCreateDraft.type] ?? null
    : null

  const createNodeInitialData = useMemo(() => {
    if (!nodeCreateDraft) {
      return {}
    }
    return getInitialNodeData(nodeCreateDraft.type)
  }, [getInitialNodeData, nodeCreateDraft])

  const confirmCreateNode = useCallback(
    async (data: Record<string, unknown>) => {
      if (!nodeCreateDraft) {
        return
      }

      setLoading(true)
      try {
        await createNodeWithData(nodeCreateDraft.type, nodeCreateDraft.position, data)
        setNodeCreateDraft(null)
      } catch (issue) {
        handleError(issue as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [createNodeWithData, handleError, nodeCreateDraft],
  )

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
    <>
      <AppShell
        email={email}
        workflowName={activeWorkflow?.name ?? 'Untitled workflow'}
        executionStatus={lastExecution?.status ?? null}
        error={error}
        loading={loading}
        onRun={handleRun}
        onLogout={handleLogout}
        onDeleteAccount={handleDeleteAccount}
        executions={executions}
        runInput={runInput}
        runEnabled={runEnabled}
        runDisabledReason={runDisabledReason}
        onError={handleError}
      >
        <WorkflowSidebar
          workflows={workflows}
          activeWorkflowId={activeWorkflowId}
          nodeCatalog={nodeCatalog}
          onSelectWorkflow={setActiveWorkflowId}
          onCreateWorkflow={handleCreateWorkflow}
          onRenameWorkflow={handleRenameWorkflow}
          onDeleteWorkflow={handleDeleteWorkflow}
          onAddNode={handleAddNode}
        />
        <GraphCanvas
          nodes={nodes}
          edges={edges}
          nodeCatalog={nodeCatalog}
          onSelectNode={setSelectedNodeId}
          onNodesChange={handleNodesChange}
          onMoveNode={handleMoveNode}
          onConnect={handleConnect}
          onDeleteEdge={handleDeleteEdge}
          onDropNode={handleDropNode}
          onDeleteNode={handleDeleteNode}
        />
        <InspectorPanel
          node={selectedNode}
          nodeCatalog={nodeCatalog}
          onSaveNode={handleUpdateNodeData}
        />
      </AppShell>

      <CreateNodeDialog
        key={
          nodeCreateDraft
            ? `${nodeCreateDraft.type}:${nodeCreateDraft.position.x}:${nodeCreateDraft.position.y}`
            : 'no-draft'
        }
        nodeSpec={createNodeSpec}
        initialData={createNodeInitialData}
        onCancel={() => setNodeCreateDraft(null)}
        onConfirm={confirmCreateNode}
      />
    </>
  )
}
