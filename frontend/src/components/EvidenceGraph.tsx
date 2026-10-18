import { useEffect, useMemo, useRef } from 'react';
import { Background, BaseEdge, Controls, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Position, ReactFlow, useNodesInitialized, useReactFlow, useStore } from '@xyflow/react';
import type { Node, NodeProps, Edge, EdgeProps } from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import EntityIcon from './EntityIcon';
import type { EvidenceGraph as Graph, GraphNode } from '../types';

type EntityData = { entity: GraphNode; inspect: (node: GraphNode) => void; [key: string]: unknown };
type EntityNode = Node<EntityData, 'entity'>;

function Entity({ data, selected }: NodeProps<EntityNode>) {
  const entity = data.entity;
  return <div className={`entity-node type-${entity.type.toLowerCase()} ${selected ? 'selected' : ''}`}>
    {[Position.Left, Position.Right, Position.Top, Position.Bottom].map(position => <Handle key={`target-${position}`} id={`target-${position}`} type="target" position={position} />)}
    <span className="entity-icon"><EntityIcon type={entity.type} size={22} /></span>
    <button className="node-text nodrag" onClick={() => data.inspect(entity)} aria-label={`Inspect ${entity.label}`}><strong title={entity.label}>{entity.label}</strong><small>{entity.type}</small></button>
    {[Position.Left, Position.Right, Position.Top, Position.Bottom].map(position => <Handle key={`source-${position}`} id={`source-${position}`} type="source" position={position} />)}
  </div>;
}

const nodeTypes = { entity: Entity };

function DetourEdge({ id, sourceX, sourceY, targetX, targetY, markerEnd, label, style }: EdgeProps) {
  // Route long same-column edges around intermediate nodes, keeping the label in the gutter.
  const path = `M ${sourceX} ${sourceY} C ${sourceX + 125} ${sourceY}, ${targetX + 125} ${targetY}, ${targetX} ${targetY}`;
  const t = 0.36;
  const labelX = sourceX + 3 * 125 * t * (1 - t);
  const labelY = sourceY + (targetY - sourceY) * (3 * t * t - 2 * t * t * t);
  return <><BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} />
    <EdgeLabelRenderer><span className="graph-edge-label" style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}>{label}</span></EdgeLabelRenderer></>;
}

const edgeTypes = { detour: DetourEdge };

function InitialFit({ visible, fitNodeIds, graphKey }: { visible: boolean; fitNodeIds: string[]; graphKey: string }) {
  const initialized = useNodesInitialized({ includeHiddenNodes: true });
  const { fitView } = useReactFlow();
  const width = useStore(state => state.width);
  const height = useStore(state => state.height);
  const fitted = useRef('');
  const key = graphKey + '/' + fitNodeIds.join('|') + (fitNodeIds.length ? `/${width}x${height}` : '');
  useEffect(() => {
    if (!visible || !initialized || !width || !height || fitted.current === key) return;
    const frame = requestAnimationFrame(() => {
      void fitView({ ...(fitNodeIds.length ? { nodes: fitNodeIds.map(id => ({ id })) } : {}),
        padding: { top: '40px', right: '25px', bottom: '55px', left: '25px' } }).then(success => { if (success) fitted.current = key; });
    });
    return () => cancelAnimationFrame(frame);
  }, [visible, initialized, width, height, fitView, fitNodeIds, key]);
  return null;
}

export default function EvidenceGraph({ graph, onSelect, selectedId, highlightedEdgeIds = [], emphasizedNodeIds = [], fitNodeIds = [], expanded = false, visible = true }: {
  graph: Graph; onSelect: (node: GraphNode) => void; selectedId?: string; highlightedEdgeIds?: string[]; emphasizedNodeIds?: string[]; fitNodeIds?: string[]; expanded?: boolean; visible?: boolean;
}) {
  const { nodes, edges } = useMemo(() => {
    const layout = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
    layout.setGraph({ rankdir: 'LR', ranksep: 120, nodesep: 65, edgesep: 30, marginx: 30, marginy: 30 });
    graph.nodes.forEach(n => layout.setNode(n.id, { width: 180, height: 72 }));
    graph.edges.forEach(e => layout.setEdge(e.source, e.target));
    dagre.layout(layout);
    // Compact semantic lanes, assigned from actual types/relationships, never entity IDs.
    // Larger or differently shaped traces retain the general-purpose Dagre layout.
    const counts = (type: string) => graph.nodes.filter(n => n.type === type).length;
    const affectedServices = graph.nodes.filter(n => n.type === 'Service' && graph.edges.some(e => e.type === 'AFFECTS' && e.target === n.id && graph.nodes.some(d => d.id === e.source && d.type === 'Decision')));
    const compact = graph.nodes.length <= 12 && counts('Decision') === 1 && counts('Person') <= 2 && affectedServices.length === 1
      && counts('Service') <= 2 && ['Incident', 'Issue', 'Message', 'Document', 'Commit', 'Repository', 'Technology'].every(type => counts(type) <= 1);
    const slots: Record<string, [number, number]> = {
      Incident: [0, 0], Issue: [340, 0], Message: [680, 0],
      Decision: [340, 150], Document: [680, 150],
      Commit: [340, 300], Repository: [680, 300], Technology: [0, 450],
    };
    let personIndex = 0;
    const positions = new Map<string, { x: number; y: number }>();
    for (const entity of graph.nodes) {
      const point = layout.node(entity.id) as { x: number; y: number };
      let position = { x: point.x - 90, y: point.y - 36 };
      if (compact) {
        const slot = slots[entity.type];
        if (slot) position = { x: slot[0], y: slot[1] };
        if (entity.type === 'Person') position = { x: 0, y: 150 + personIndex++ * 150 };
        if (entity.type === 'Service') {
          const affected = graph.edges.some(e => e.type === 'AFFECTS' && e.target === entity.id && graph.nodes.some(n => n.id === e.source && n.type === 'Decision'));
          position = { x: affected ? 340 : 680, y: 450 };
        }
      }
      positions.set(entity.id, position);
    }
    const nodes: EntityNode[] = graph.nodes.map(entity => {
      return { id: entity.id, type: 'entity', position: positions.get(entity.id)!, width: 180, height: 72,
        data: { entity, inspect: onSelect }, ariaLabel: `${entity.label}, ${entity.type}`, draggable: false };
    });
    const edges: Edge[] = graph.edges.map(e => {
      const from = positions.get(e.source)!;
      const to = positions.get(e.target)!;
      const dx = to.x - from.x, dy = to.y - from.y;
      let source = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? Position.Right : Position.Left) : (dy > 0 ? Position.Bottom : Position.Top);
      let target = ({ left: Position.Right, right: Position.Left, top: Position.Bottom, bottom: Position.Top })[source];
      // Separate parallel inverse relationships so both labels remain inspectable.
      if (e.type === 'SUPPORTED_BY' && graph.edges.some(other => other.source === e.target && other.target === e.source)) {
        source = Position.Right; target = Position.Right;
      }
      if (compact && Math.abs(dx) < 1 && Math.abs(dy) > 180) {
        source = Position.Right; target = Position.Right;
      }
      return {
      id: e.id, source: e.source, target: e.target, label: e.type,
      type: compact && Math.abs(dx) < 1 && Math.abs(dy) > 180 ? 'detour' : 'default',
      sourceHandle: `source-${source}`, targetHandle: `target-${target}`,
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#7b9181' },
      style: { stroke: '#7b9181', strokeWidth: 1.3 },
      labelStyle: { fontSize: 10, fill: '#43534a' }, labelBgStyle: { fill: '#fafbf8', fillOpacity: 0.96 },
      labelBgPadding: [6, 4], labelBgBorderRadius: 5,
      ariaLabel: `${e.source} ${e.type} ${e.target}`,
    }; });
    return { nodes, edges };
  }, [graph, onSelect]);

  // Selection changes styling only; layout and the React Flow viewport stay intact.
  const highlighted = useMemo(() => {
    const neighbors = new Set([selectedId]);
    graph.edges.forEach(e => { if (e.source === selectedId) neighbors.add(e.target); if (e.target === selectedId) neighbors.add(e.source); });
    return {
      nodes: nodes.map(node => ({ ...node, selected: node.id === selectedId,
        className: selectedId && neighbors.has(node.id) ? 'connected-node' : '',
        style: { opacity: selectedId ? (!neighbors.has(node.id) ? 0.75 : 1) : emphasizedNodeIds.length && !emphasizedNodeIds.includes(node.id) ? 0.65 : 1 } })),
      edges: edges.map(edge => {
        const connected = highlightedEdgeIds.length ? highlightedEdgeIds.includes(edge.id) : edge.source === selectedId || edge.target === selectedId;
        return { ...edge, style: { ...edge.style, stroke: connected ? '#315d48' : '#7b9181', strokeWidth: connected ? 2.4 : 1.3, opacity: selectedId && !connected ? 0.55 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: connected ? '#315d48' : '#7b9181' } };
      }),
    };
  }, [nodes, edges, graph.edges, selectedId, highlightedEdgeIds, emphasizedNodeIds]);

  if (!graph.nodes.length) return <div className="graph-empty"><GitEmpty />No connected graph evidence was returned.</div>;
  return <div className={`graph-canvas ${expanded ? 'expanded' : ''}`} aria-label="Evidence graph">
    <div className="graph-legend" aria-label="Entity types">
      {Array.from(new Set(graph.nodes.map(n => n.type))).map(type =>
        <span className={`type-${type.toLowerCase()}`} key={type}><i />{type}</span>)}
    </div>
    <ReactFlow nodes={highlighted.nodes} edges={highlighted.edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
      minZoom={0.25} maxZoom={1.6} nodesConnectable={false} edgesFocusable={false}
      onNodeClick={(_event, node) => onSelect(node.data.entity)}>
      <InitialFit visible={visible} fitNodeIds={fitNodeIds} graphKey={graph.nodes.map(n => n.id).join('|')} />
      <Background color="#dce4da" gap={22} size={1} />
      <Controls showInteractive={false} />
      {expanded && <MiniMap pannable zoomable nodeColor="#cedbcd" />}
    </ReactFlow>
    <span className="graph-hint">Scroll to zoom · drag to pan · select a node to inspect</span>
  </div>;
}

function GitEmpty() { return <EntityIcon type="Relationship" size={32} />; }
