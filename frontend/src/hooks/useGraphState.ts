import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Edge, Node as FlowNode, NodeChange } from 'reactflow'
import { MarkerType, applyNodeChanges } from 'reactflow'

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
  NodeCatalogItem,
  NodeCreatePayload,
  NodeResponse,
  NodeType,
} from '../lib/types'

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
  selectedNodeId: string | null
  selectedNode: FlowNode | null
  clearGraphState: () => void
  setSelectedNodeId: (value: string | null) => void
  createNodeWithData: (
    type: NodeType,
    position: { x: number; y: number },
    data: Record<string, unknown>,
  ) => Promise<void>
  getInitialNodeData: (type: NodeType) => Record<string, unknown>
  handleDeleteNode: (nodeId: string) => Promise<void>
  handleUpdateNodeData: (nodeId: string, data: Record<string, unknown>) => Promise<void>
  handleNodesChange: (changes: NodeChange[]) => void
  handleMoveNode: (nodeId: string, x: number, y: number) => Promise<void>
  handleConnect: (sourceId: string, targetId: string) => Promise<void>
  handleDeleteEdge: (edgeId: string) => Promise<void>
}

function toFlowEdge(edge: {
  id: number
  source_node_id: number
  target_node_id: number
}): Edge {
  return {
    id: String(edge.id),
    source: String(edge.source_node_id),
    target: String(edge.target_node_id),
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
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  )

  useEffect(() => {
    if (!token || !activeWorkflowId) {
      setNodes([])
      setEdges([])
      setSelectedNodeId(null)
      return
    }

    setLoading(true)
    Promise.all([getNodes(activeWorkflowId), getEdges(activeWorkflowId)])
      .then(([nodeItems, edgeItems]) => {
        setNodes(
          nodeItems.map((node) => toFlowNode(node, nodeCatalogByType)),
        )
        setEdges(
          edgeItems.map((edge) => toFlowEdge(edge)),
        )
      })
      .catch((error: ApiError) => handleError(error))
      .finally(() => setLoading(false))
  }, [activeWorkflowId, handleError, nodeCatalogByType, setLoading, token])

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

      const created = await createNode(payload)
      setNodes((previous) => [
        ...previous,
        toFlowNode(created, nodeCatalogByType),
      ])
      setSelectedNodeId(String(created.id))
      setError(null)
    },
    [activeWorkflowId, handleError, nodeCatalogByType, setError],
  )

  const handleDeleteNode = useCallback(
    async (nodeId: string): Promise<void> => {
      try {
        await deleteNode(Number(nodeId))
        setNodes((previous) => previous.filter((node) => node.id !== nodeId))
        setEdges((previous) =>
          previous.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
        )
        if (selectedNodeId === nodeId) {
          setSelectedNodeId(null)
        }
      } catch (error) {
        handleError(error as ApiError)
      }
    },
    [handleError, selectedNodeId],
  )

  const handleUpdateNodeData = useCallback(
    async (nodeId: string, data: Record<string, unknown>): Promise<void> => {
      try {
        const { nodeType: _nodeType, iconKey: _iconKey, graph: _graph, ...cleanData } = data
        void _nodeType
        void _iconKey
        void _graph

        const updated = await updateNode(Number(nodeId), { data: cleanData })
        setNodes((previous) =>
          previous.map((node) =>
            node.id === nodeId
              ? toFlowNode(updated, nodeCatalogByType)
              : node,
          ),
        )
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      }
    },
    [handleError, nodeCatalogByType, setError],
  )

  const handleNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((previous) => applyNodeChanges(changes, previous))
  }, [])

  const handleMoveNode = useCallback(
    async (nodeId: string, x: number, y: number): Promise<void> => {
      try {
        await updateNode(Number(nodeId), { position_x: x, position_y: y })
      } catch (error) {
        handleError(error as ApiError)
      }
    },
    [handleError],
  )

  const handleConnect = useCallback(
    async (sourceId: string, targetId: string): Promise<void> => {
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
        setEdges((previous) => [
          ...previous,
          toFlowEdge(created),
        ])
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [activeWorkflowId, handleError, setError, setLoading],
  )

  const handleDeleteEdge = useCallback(
    async (edgeId: string): Promise<void> => {
      setLoading(true)
      try {
        await deleteEdge(Number(edgeId))
        setEdges((previous) => previous.filter((edge) => edge.id !== edgeId))
        setError(null)
      } catch (error) {
        handleError(error as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [handleError, setError, setLoading],
  )

  const clearGraphState = useCallback(() => {
    setNodes([])
    setEdges([])
    setSelectedNodeId(null)
  }, [])

  return {
    nodes,
    edges,
    selectedNodeId,
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
  }
}
