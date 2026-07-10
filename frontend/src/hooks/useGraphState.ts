import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Edge, Node as FlowNode, NodeChange } from 'reactflow'
import { MarkerType, applyNodeChanges } from 'reactflow'

import { computeAutoLayout } from '../lib/autoLayout'
import {
  createEdge,
  createNode,
  deleteEdge,
  deleteNode,
  getEdges,
  getNodes,
  updateNode,
} from '../lib/api'
import type {
  ApiError,
  EdgeCreatePayload,
  NodeCatalogItem,
  NodeCreatePayload,
  NodeResponse,
  NodeType,
} from '../lib/types'
import { type UndoableCommand, useUndoRedo } from './useUndoRedo'

interface UseGraphStateParams {
  token: string | null
  activeWorkflowId: number | null
  nodeCatalogByType: Record<string, NodeCatalogItem>
  setLoading: (value: boolean) => void
  setError: (value: string | null) => void
  handleError: (error: ApiError) => void
}

interface UseGraphStateResult {
  nodes: FlowNode[]
  edges: Edge[]
  selectedNodeIds: string[]
  selectedEdgeIds: string[]
  selectedNode: FlowNode | null
  canUndo: boolean
  canRedo: boolean
  clearGraphState: () => void
  handleSelectionChange: (nodeIds: string[], edgeIds: string[]) => void
  createNodeWithData: (
    type: NodeType,
    position: { x: number; y: number },
    data: Record<string, unknown>,
  ) => Promise<void>
  getInitialNodeData: (type: NodeType) => Record<string, unknown>
  handleDeleteNode: (nodeId: string) => Promise<void>
  handleDeleteSelected: () => Promise<void>
  handleUpdateNodeData: (nodeId: string, data: Record<string, unknown>) => Promise<boolean>
  handleNodesChange: (changes: NodeChange[]) => void
  handleMoveNode: (nodeId: string, x: number, y: number) => Promise<void>
  handleConnect: (
    sourceId: string,
    targetId: string,
    sourceHandle: string | null,
  ) => Promise<void>
  handleDeleteEdge: (edgeId: string) => Promise<void>
  copySelection: () => void
  pasteClipboard: () => Promise<void>
  handleAutoLayout: () => Promise<void>
  undo: () => Promise<void>
  redo: () => Promise<void>
}

// Position clones are offset by this much so repeated pastes fan out
// visibly instead of stacking exactly on top of the originals.
const PASTE_OFFSET = 40

interface GraphMutators {
  setNodes: React.Dispatch<React.SetStateAction<FlowNode[]>>
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>
}

function toFlowEdge(edge: {
  id: number
  source_node_id: number
  target_node_id: number
  source_handle?: string | null
}): Edge {
  return {
    id: String(edge.id),
    source: String(edge.source_node_id),
    target: String(edge.target_node_id),
    sourceHandle: edge.source_handle ?? undefined,
    type: 'step',
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 12,
      height: 12,
      color: '#35ffbc',
    },
    className: 'pixel-edge',
    style: {
      strokeWidth: 2.5,
      stroke: '#35ffbc',
    },
  }
}

function toFlowNode(
  node: NodeResponse,
  nodeCatalogByType: Record<string, NodeCatalogItem>,
): FlowNode {
  const catalogNode = nodeCatalogByType[node.type]

  return {
    id: String(node.id),
    type: node.type,
    position: { x: node.position_x, y: node.position_y },
    data: {
      ...node.data,
      label: node.data?.label ?? `${node.type} node`,
      nodeType: node.type,
      iconKey: catalogNode?.icon_key ?? 'input',
      graph: catalogNode?.graph ?? { has_input: true, has_output: true },
    },
  }
}

function buildDefaultData(catalogNode: NodeCatalogItem): Record<string, unknown> {
  const data: Record<string, unknown> = {}

  for (const field of catalogNode.fields) {
    if (field.ui.widget === 'optional_number') {
      data[field.name] = null
      continue
    }

    if (field.default !== null && field.default !== undefined) {
      data[field.name] = field.default
      continue
    }

    if (field.validators.select?.length) {
      data[field.name] = field.validators.select[0]
      continue
    }

    if (field.validators.ge !== undefined) {
      data[field.name] = field.validators.ge
      continue
    }

    if (field.ui.widget === 'number') {
      data[field.name] = 0
      continue
    }

    data[field.name] = ''
  }

  return data
}

// Node objects carry a few frontend-only fields (mirrored from the node
// catalog) alongside the real, persisted config fields — strip them before
// sending `data` back to the API.
function stripSyntheticFields(data: Record<string, unknown>): Record<string, unknown> {
  const { nodeType: _nodeType, iconKey: _iconKey, graph: _graph, ...cleanData } = data
  void _nodeType
  void _iconKey
  void _graph
  return cleanData
}

// --- Command factories -----------------------------------------------
// Each command remembers its *current* server-assigned ID in a closure
// variable (not React state) so it stays correct across repeated
// undo/redo cycles — a redone "create" gets a brand new ID every time.

function makeCreateNodeCommand(
  payload: NodeCreatePayload,
  nodeCatalogByType: Record<string, NodeCatalogItem>,
  mutators: GraphMutators,
  onCreated?: (id: string) => void,
): UndoableCommand {
  let currentId: string | null = null

  const execute = async (): Promise<void> => {
    const created = await createNode(payload)
    currentId = String(created.id)
    mutators.setNodes((previous) => [...previous, toFlowNode(created, nodeCatalogByType)])
    onCreated?.(currentId)
  }

  return {
    label: `Create ${payload.type} node`,
    execute,
    undo: async () => {
      if (!currentId) {
        return
      }
      const deletedId = currentId
      await deleteNode(Number(deletedId))
      mutators.setNodes((previous) => previous.filter((node) => node.id !== deletedId))
      mutators.setEdges((previous) =>
        previous.filter((edge) => edge.source !== deletedId && edge.target !== deletedId),
      )
      currentId = null
    },
  }
}

function makeCreateEdgeCommand(
  payload: EdgeCreatePayload,
  mutators: Pick<GraphMutators, 'setEdges'>,
  onCreated?: (id: string) => void,
): UndoableCommand {
  let currentId: string | null = null

  const execute = async (): Promise<void> => {
    const created = await createEdge(payload)
    currentId = String(created.id)
    mutators.setEdges((previous) => [...previous, toFlowEdge(created)])
    onCreated?.(currentId)
  }

  return {
    label: 'Create edge',
    execute,
    undo: async () => {
      if (!currentId) {
        return
      }
      const deletedId = currentId
      await deleteEdge(Number(deletedId))
      mutators.setEdges((previous) => previous.filter((edge) => edge.id !== deletedId))
      currentId = null
    },
  }
}

// Deletes one or more nodes (plus every edge touching any of them) as a
// single atomic command. Handling a batch in one command — rather than
// composing N independent per-node commands — matters when the deleted
// nodes were connected *to each other*: on undo, all nodes must be
// recreated first (building a fresh original-id -> new-id map) before any
// of their edges are recreated, since an edge between two deleted nodes
// needs both endpoints' new ids. An edge crossing to a node outside the
// deleted set falls back to that node's (unchanged) original id.
function makeDeleteNodesCommand(
  nodesToDelete: FlowNode[],
  touchingEdges: Edge[],
  workflowId: number,
  nodeCatalogByType: Record<string, NodeCatalogItem>,
  mutators: GraphMutators,
): UndoableCommand {
  const nodeSnapshots = nodesToDelete.map((node) => ({
    originalId: node.id,
    type: String(node.data?.nodeType ?? node.type),
    data: stripSyntheticFields((node.data as Record<string, unknown>) ?? {}),
    position: { x: node.position.x, y: node.position.y },
  }))
  const edgeSnapshots = touchingEdges.map((edge) => ({
    originalSource: edge.source,
    originalTarget: edge.target,
    sourceHandle: edge.sourceHandle ?? null,
  }))

  let currentIdByOriginal = new Map<string, string>(
    nodeSnapshots.map((snapshot) => [snapshot.originalId, snapshot.originalId]),
  )

  const label =
    nodeSnapshots.length === 1
      ? `Delete ${nodeSnapshots[0].type} node`
      : `Delete ${nodeSnapshots.length} nodes`

  return {
    label,
    execute: async () => {
      const idsToDelete = nodeSnapshots
        .map((snapshot) => currentIdByOriginal.get(snapshot.originalId))
        .filter((id): id is string => id !== undefined)
      for (const id of idsToDelete) {
        await deleteNode(Number(id))
      }
      // The DB cascade-deletes connected edges; mirror that locally.
      const deletedSet = new Set(idsToDelete)
      mutators.setNodes((previous) => previous.filter((node) => !deletedSet.has(node.id)))
      mutators.setEdges((previous) =>
        previous.filter((edge) => !deletedSet.has(edge.source) && !deletedSet.has(edge.target)),
      )
    },
    undo: async () => {
      const freshIdByOriginal = new Map<string, string>()
      for (const snapshot of nodeSnapshots) {
        const created = await createNode({
          workflow_id: workflowId,
          type: snapshot.type,
          data: snapshot.data,
          position_x: snapshot.position.x,
          position_y: snapshot.position.y,
        })
        freshIdByOriginal.set(snapshot.originalId, String(created.id))
        mutators.setNodes((previous) => [...previous, toFlowNode(created, nodeCatalogByType)])
      }
      currentIdByOriginal = freshIdByOriginal

      for (const snapshot of edgeSnapshots) {
        const sourceId = freshIdByOriginal.get(snapshot.originalSource) ?? snapshot.originalSource
        const targetId = freshIdByOriginal.get(snapshot.originalTarget) ?? snapshot.originalTarget
        const createdEdge = await createEdge({
          workflow_id: workflowId,
          source_node_id: Number(sourceId),
          target_node_id: Number(targetId),
          source_handle: snapshot.sourceHandle,
        })
        mutators.setEdges((previous) => [...previous, toFlowEdge(createdEdge)])
      }
    },
  }
}

function makeDeleteEdgeCommand(
  edge: Edge,
  workflowId: number,
  mutators: Pick<GraphMutators, 'setEdges'>,
): UndoableCommand {
  const sourceId = edge.source
  const targetId = edge.target
  const sourceHandle = edge.sourceHandle ?? null
  let currentEdgeId: string | null = edge.id

  return {
    label: 'Delete edge',
    execute: async () => {
      if (!currentEdgeId) {
        return
      }
      const deletedId = currentEdgeId
      await deleteEdge(Number(deletedId))
      mutators.setEdges((previous) => previous.filter((e) => e.id !== deletedId))
      currentEdgeId = null
    },
    undo: async () => {
      const created = await createEdge({
        workflow_id: workflowId,
        source_node_id: Number(sourceId),
        target_node_id: Number(targetId),
        source_handle: sourceHandle,
      })
      currentEdgeId = String(created.id)
      mutators.setEdges((previous) => [...previous, toFlowEdge(created)])
    },
  }
}

function makeMoveNodeCommand(
  nodeId: string,
  from: { x: number; y: number },
  to: { x: number; y: number },
  mutators: Pick<GraphMutators, 'setNodes'>,
): UndoableCommand {
  const applyPosition = async (position: { x: number; y: number }): Promise<void> => {
    await updateNode(Number(nodeId), { position_x: position.x, position_y: position.y })
    mutators.setNodes((previous) =>
      previous.map((node) => (node.id === nodeId ? { ...node, position } : node)),
    )
  }

  return {
    label: 'Move node',
    execute: () => applyPosition(to),
    undo: () => applyPosition(from),
  }
}

function makeCompositeCommand(label: string, commands: UndoableCommand[]): UndoableCommand {
  return {
    label,
    execute: async () => {
      for (const command of commands) {
        await command.execute()
      }
    },
    undo: async () => {
      for (let i = commands.length - 1; i >= 0; i -= 1) {
        await commands[i].undo()
      }
    },
  }
}

export function useGraphState({
  token,
  activeWorkflowId,
  nodeCatalogByType,
  setLoading,
  setError,
  handleError,
}: UseGraphStateParams): UseGraphStateResult {
  const [nodes, setNodes] = useState<FlowNode[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([])
  const [selectedEdgeIds, setSelectedEdgeIds] = useState<string[]>([])
  const clipboardRef = useRef<{ nodes: FlowNode[]; edges: Edge[] } | null>(null)
  const { canUndo, canRedo, pushCommand, undo, redo, clear: clearHistory } = useUndoRedo()

  const selectedNodeId = selectedNodeIds.length === 1 ? selectedNodeIds[0] : null
  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  )

  useEffect(() => {
    if (!token || !activeWorkflowId) {
      setNodes([])
      setEdges([])
      setSelectedNodeIds([])
      setSelectedEdgeIds([])
      clearHistory()
      return
    }

    setLoading(true)
    clearHistory()
    Promise.all([getNodes(activeWorkflowId), getEdges(activeWorkflowId)])
      .then(([nodeItems, edgeItems]) => {
        setNodes(
          nodeItems.map((node) => toFlowNode(node, nodeCatalogByType)),
        )
        setEdges(
          edgeItems.map((edge) => toFlowEdge(edge)),
        )
        setSelectedNodeIds([])
        setSelectedEdgeIds([])
      })
      .catch((error: ApiError) => handleError(error))
      .finally(() => setLoading(false))
  }, [activeWorkflowId, clearHistory, handleError, nodeCatalogByType, setLoading, token])

  const getInitialNodeData = useCallback(
    (type: NodeType): Record<string, unknown> => {
      const catalogNode = nodeCatalogByType[type]
      if (!catalogNode) {
        return {}
      }
      return buildDefaultData(catalogNode)
    },
    [nodeCatalogByType],
  )

  const createNodeWithData = useCallback(
    async (
      type: NodeType,
      position: { x: number; y: number },
      data: Record<string, unknown>,
    ): Promise<void> => {
      if (!activeWorkflowId) {
        return
      }

      const catalogNode = nodeCatalogByType[type]
      if (!catalogNode) {
        handleError({ message: `Unknown node type: ${type}`, status: 400 })
        return
      }

      const payload: NodeCreatePayload = {
        workflow_id: activeWorkflowId,
        type,
        data,
        position_x: position.x,
        position_y: position.y,
      }

      let createdId: string | null = null
      const command = makeCreateNodeCommand(
        payload,
        nodeCatalogByType,
        { setNodes, setEdges },
        (id) => {
          createdId = id
        },
      )
      // Errors intentionally propagate — `confirmCreateNode` in App.tsx
      // relies on the rejection to keep the create-node dialog open.
      await command.execute()
      setSelectedNodeIds(createdId ? [createdId] : [])
      setSelectedEdgeIds([])
      setError(null)
      pushCommand(command)
    },
    [activeWorkflowId, handleError, nodeCatalogByType, pushCommand, setError],
  )

  const handleDeleteNode = useCallback(
    async (nodeId: string): Promise<void> => {
      const node = nodes.find((n) => n.id === nodeId)
      if (!node || !activeWorkflowId) {
        return
      }
      const connectedEdges = edges.filter(
        (edge) => edge.source === nodeId || edge.target === nodeId,
      )
      const command = makeDeleteNodesCommand(
        [node],
        connectedEdges,
        activeWorkflowId,
        nodeCatalogByType,
        { setNodes, setEdges },
      )
      try {
        await command.execute()
        setSelectedNodeIds((previous) => previous.filter((id) => id !== nodeId))
        pushCommand(command)
      } catch (error) {
        handleError(error as ApiError)
      }
    },
    [activeWorkflowId, edges, handleError, nodeCatalogByType, nodes, pushCommand],
  )

  const handleDeleteSelected = useCallback(async (): Promise<void> => {
    if (!activeWorkflowId) {
      return
    }
    const nodeIdsToDelete = new Set(selectedNodeIds)
    // Edges touching a selected node are already captured by that node's
    // own delete command (and cascade-deleted server-side) — only handle
    // edges selected independently of any selected node here.
    const independentEdges = edges.filter(
      (edge) =>
        selectedEdgeIds.includes(edge.id) &&
        !nodeIdsToDelete.has(edge.source) &&
        !nodeIdsToDelete.has(edge.target),
    )

    const nodesToDelete = [...nodeIdsToDelete]
      .map((nodeId) => nodes.find((n) => n.id === nodeId))
      .filter((node): node is FlowNode => node !== undefined)
    // Every edge touching any of the deleted nodes — both edges internal to
    // the deleted set and edges crossing to a surviving node — so the batch
    // command can remap/restore them correctly on undo (see
    // `makeDeleteNodesCommand`).
    const touchingEdges = edges.filter(
      (edge) => nodeIdsToDelete.has(edge.source) || nodeIdsToDelete.has(edge.target),
    )

    const commands: UndoableCommand[] = []
    if (nodesToDelete.length > 0) {
      commands.push(
        makeDeleteNodesCommand(nodesToDelete, touchingEdges, activeWorkflowId, nodeCatalogByType, {
          setNodes,
          setEdges,
        }),
      )
    }
    for (const edge of independentEdges) {
      commands.push(makeDeleteEdgeCommand(edge, activeWorkflowId, { setEdges }))
    }

    if (commands.length === 0) {
      return
    }

    try {
      for (const command of commands) {
        await command.execute()
      }
      setSelectedNodeIds([])
      setSelectedEdgeIds([])
      pushCommand(
        commands.length === 1
          ? commands[0]
          : makeCompositeCommand(`Delete ${commands.length} item(s)`, commands),
      )
    } catch (error) {
      handleError(error as ApiError)
    }
  }, [
    activeWorkflowId,
    edges,
    handleError,
    nodeCatalogByType,
    nodes,
    pushCommand,
    selectedEdgeIds,
    selectedNodeIds,
  ])

  const handleUpdateNodeData = useCallback(
    async (nodeId: string, data: Record<string, unknown>): Promise<boolean> => {
      try {
        const cleanData = stripSyntheticFields(data)
        const updated = await updateNode(Number(nodeId), { data: cleanData })
        setNodes((previous) =>
          previous.map((node) =>
            node.id === nodeId
              ? // Preserve React Flow's selection flag: the rebuilt node would
                // otherwise come back unselected, deselecting it mid-edit and
                // closing the Inspector right after the first valid save.
                { ...toFlowNode(updated, nodeCatalogByType), selected: node.selected }
              : node,
          ),
        )
        setError(null)
        return true
      } catch (error) {
        handleError(error as ApiError)
        return false
      }
    },
    [handleError, nodeCatalogByType, setError],
  )

  const handleNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((previous) => applyNodeChanges(changes, previous))
  }, [])

  const handleMoveNode = useCallback(
    async (nodeId: string, x: number, y: number): Promise<void> => {
      const node = nodes.find((n) => n.id === nodeId)
      if (!node) {
        return
      }
      const from = { x: node.position.x, y: node.position.y }
      const to = { x, y }
      if (from.x === to.x && from.y === to.y) {
        return
      }

      const command = makeMoveNodeCommand(nodeId, from, to, { setNodes })
      try {
        await command.execute()
        pushCommand(command)
      } catch (error) {
        handleError(error as ApiError)
      }
    },
    [handleError, nodes, pushCommand],
  )

  const handleConnect = useCallback(
    async (
      sourceId: string,
      targetId: string,
      sourceHandle: string | null,
    ): Promise<void> => {
      if (!activeWorkflowId) {
        return
      }

      setLoading(true)
      const command = makeCreateEdgeCommand(
        {
          workflow_id: activeWorkflowId,
          source_node_id: Number(sourceId),
          target_node_id: Number(targetId),
          source_handle: sourceHandle,
        },
        { setEdges },
      )
      try {
        await command.execute()
        setError(null)
        pushCommand(command)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [activeWorkflowId, handleError, pushCommand, setError, setLoading],
  )

  const handleDeleteEdge = useCallback(
    async (edgeId: string): Promise<void> => {
      const edge = edges.find((e) => e.id === edgeId)
      if (!edge || !activeWorkflowId) {
        return
      }
      const command = makeDeleteEdgeCommand(edge, activeWorkflowId, { setEdges })
      setLoading(true)
      try {
        await command.execute()
        setSelectedEdgeIds((previous) => previous.filter((id) => id !== edgeId))
        setError(null)
        pushCommand(command)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [activeWorkflowId, edges, handleError, pushCommand, setError, setLoading],
  )

  const handleSelectionChange = useCallback((nodeIds: string[], edgeIds: string[]) => {
    setSelectedNodeIds(nodeIds)
    setSelectedEdgeIds(edgeIds)
  }, [])

  const copySelection = useCallback(() => {
    if (selectedNodeIds.length === 0) {
      return
    }
    const idSet = new Set(selectedNodeIds)
    clipboardRef.current = {
      nodes: nodes.filter((node) => idSet.has(node.id)),
      edges: edges.filter((edge) => idSet.has(edge.source) && idSet.has(edge.target)),
    }
  }, [edges, nodes, selectedNodeIds])

  const pasteClipboard = useCallback(async (): Promise<void> => {
    const clipboard = clipboardRef.current
    if (!clipboard || clipboard.nodes.length === 0 || !activeWorkflowId) {
      return
    }

    const idMap = new Map<string, string>()
    const commands: UndoableCommand[] = []
    const newSelection: string[] = []

    try {
      for (const node of clipboard.nodes) {
        const type = String(node.data?.nodeType ?? node.type)
        const command = makeCreateNodeCommand(
          {
            workflow_id: activeWorkflowId,
            type,
            data: stripSyntheticFields((node.data as Record<string, unknown>) ?? {}),
            position_x: node.position.x + PASTE_OFFSET,
            position_y: node.position.y + PASTE_OFFSET,
          },
          nodeCatalogByType,
          { setNodes, setEdges },
          (newId) => {
            idMap.set(node.id, newId)
            newSelection.push(newId)
          },
        )
        await command.execute()
        commands.push(command)
      }

      for (const edge of clipboard.edges) {
        const newSource = idMap.get(edge.source)
        const newTarget = idMap.get(edge.target)
        if (!newSource || !newTarget) {
          continue
        }
        const command = makeCreateEdgeCommand(
          {
            workflow_id: activeWorkflowId,
            source_node_id: Number(newSource),
            target_node_id: Number(newTarget),
            source_handle: edge.sourceHandle ?? null,
          },
          { setEdges },
        )
        await command.execute()
        commands.push(command)
      }

      setSelectedNodeIds(newSelection)
      setSelectedEdgeIds([])
      setError(null)
      pushCommand(makeCompositeCommand(`Paste ${clipboard.nodes.length} node(s)`, commands))
    } catch (error) {
      handleError(error as ApiError)
    }
  }, [activeWorkflowId, handleError, nodeCatalogByType, pushCommand, setError])

  const handleAutoLayout = useCallback(async (): Promise<void> => {
    if (nodes.length === 0) {
      return
    }
    const positions = computeAutoLayout(nodes, edges)
    const commands = nodes
      .map((node) => {
        const next = positions.get(node.id)
        if (!next) {
          return null
        }
        const from = { x: node.position.x, y: node.position.y }
        if (Math.abs(from.x - next.x) < 1 && Math.abs(from.y - next.y) < 1) {
          return null
        }
        return makeMoveNodeCommand(node.id, from, next, { setNodes })
      })
      .filter((command): command is UndoableCommand => command !== null)

    if (commands.length === 0) {
      return
    }

    try {
      await Promise.all(commands.map((command) => command.execute()))
      pushCommand(makeCompositeCommand('Auto-layout', commands))
    } catch (error) {
      handleError(error as ApiError)
    }
  }, [edges, handleError, nodes, pushCommand])

  const clearGraphState = useCallback(() => {
    setNodes([])
    setEdges([])
    setSelectedNodeIds([])
    setSelectedEdgeIds([])
    clipboardRef.current = null
    clearHistory()
  }, [clearHistory])

  return {
    nodes,
    edges,
    selectedNodeIds,
    selectedEdgeIds,
    selectedNode,
    canUndo,
    canRedo,
    clearGraphState,
    handleSelectionChange,
    createNodeWithData,
    getInitialNodeData,
    handleDeleteNode,
    handleDeleteSelected,
    handleUpdateNodeData,
    handleNodesChange,
    handleMoveNode,
    handleConnect,
    handleDeleteEdge,
    copySelection,
    pasteClipboard,
    handleAutoLayout,
    undo,
    redo,
  }
}
