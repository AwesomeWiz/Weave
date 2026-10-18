import { useCallback, useEffect, useMemo, useRef } from 'react';
import { Background, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow, useNodesInitialized, useReactFlow, useStore } from '@xyflow/react';
import type { Node, NodeProps, Edge } from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import EntityIcon from './EntityIcon';
import type { EvidenceGraph as Graph, GraphNode, TraceSequence } from '../types';
import type { TraceClock } from '../traceClock';
import { traceEntityName, traceRelationshipLabel } from '../tracePresentation';
import { useTraceClockState } from '../useTracePlayback';
import { TraceEdge, TraceDetourEdge } from './TraceEdge';

type EntityData = { entity: GraphNode; inspect: (node: GraphNode) => void; cinematic?: boolean; clock?: TraceClock; arriving?: boolean; [key: string]: unknown };
type EntityNode = Node<EntityData, 'entity'>;

function Entity({ data, selected }: NodeProps<EntityNode>) {
  const entity = data.entity;
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!data.clock || !data.arriving) return;
    return data.clock.subscribeFrame(progress => { if (ref.current) ref.current.dataset.arrived = progress >= 0.85 ? 'true' : 'false'; });
  }, [data.clock, data.arriving]);
  const label = traceEntityName(entity, entity.id);
  return <div ref={ref} className={`entity-node type-${entity.type.toLowerCase()} ${selected ? 'selected' : ''}`}>
    {[Position.Left, Position.Right, Position.Top, Position.Bottom].map(position => <Handle key={`target-${position}`} id={`target-${position}`} type="target" position={position} />)}
    <span className="entity-icon"><EntityIcon type={entity.type} size={22} /></span>
    <button className="node-text nodrag" onClick={() => data.inspect(entity)} aria-label={`Inspect ${label}`}><strong title={label}>{label}</strong><small>{entity.type}</small></button>
    {[Position.Left, Position.Right, Position.Top, Position.Bottom].map(position => <Handle key={`source-${position}`} id={`source-${position}`} type="source" position={position} />)}
  </div>;
}

const nodeTypes = { entity: Entity };

const edgeTypes = { default: TraceEdge, detour: TraceDetourEdge };

function FitGraph({ manual }: { manual: { current: boolean } }) {
  const { fitView } = useReactFlow();
  return <button className="button small fit-graph" onClick={() => { manual.current = true; void fitView({ padding: 0.2 }); }}>Fit graph</button>;
}

function InitialFit({ visible, fitNodeIds, graphKey, clock, manual }: { visible: boolean; fitNodeIds: string[]; graphKey: string; clock?: TraceClock | null; manual: { current: boolean } }) {
  const initialized = useNodesInitialized({ includeHiddenNodes: true });
  const { fitView, getViewport, setViewport } = useReactFlow();
  const width = useStore(state => state.width);
  const height = useStore(state => state.height);
  const fitted = useRef('');
  const state = useTraceClockState(clock);
  const reset = useRef({ clock, key: state.cameraReset });
  const key = graphKey + '/' + fitNodeIds.join('|') + (fitNodeIds.length ? `/${width}x${height}` : '') + '/' + state.cameraReset;
  const wasPlaying = useRef(state.playing);
  const pausedFrame = useRef<string | null>(null);
  useEffect(() => {
    if (reset.current.clock !== clock) { wasPlaying.current = state.playing; pausedFrame.current = null; }
    if (clock && wasPlaying.current && !state.playing) {
      pausedFrame.current = key;
      void setViewport(getViewport(), { duration: 0 });
    } else if (clock && !wasPlaying.current && state.playing && pausedFrame.current === key) {
      pausedFrame.current = null; fitted.current = '';
    }
    wasPlaying.current = state.playing;
  }, [clock, key, state.playing, getViewport, setViewport]);
  useEffect(() => {
    if (reset.current.clock !== clock || reset.current.key !== state.cameraReset) {
      manual.current = false; reset.current = { clock, key: state.cameraReset }; fitted.current = ''; pausedFrame.current = null;
    }
    if (clock && !state.playing && pausedFrame.current === key) return;
    if (clock && manual.current) return;
    if (!visible || !initialized || !width || !height || fitted.current === key) return;
    const frame = requestAnimationFrame(() => {
      if (clock && manual.current) return;
      void fitView({ ...(fitNodeIds.length ? { nodes: fitNodeIds.map(id => ({ id })) } : {}),
        ...(clock ? { duration: state.reduced ? 0 : 450, minZoom: 0.55, maxZoom: 1.1 } : {}),
        padding: clock ? { top: '55px', right: '35px', bottom: '70px', left: '35px' }
          : { top: '40px', right: '25px', bottom: '55px', left: '25px' } }).then(success => { if (success) fitted.current = key; });
    });
    return () => cancelAnimationFrame(frame);
  }, [visible, initialized, width, height, fitView, fitNodeIds, key, clock, state.cameraReset, state.reduced, state.playing, manual]);
  return null;
}

export default function EvidenceGraph({ graph, onSelect, selectedId, highlightedEdgeIds = [], emphasizedNodeIds = [], traceNodeIds = [], fitNodeIds = [], expanded = false, visible = true, trace, clock }: {
  graph: Graph; onSelect: (node: GraphNode) => void; selectedId?: string; highlightedEdgeIds?: string[]; emphasizedNodeIds?: string[]; traceNodeIds?: string[]; fitNodeIds?: string[]; expanded?: boolean; visible?: boolean;
  trace?: { sequence: TraceSequence; index: number }; clock?: TraceClock | null;
}) {
  const select = useRef(onSelect);
  useEffect(() => { select.current = onSelect; }, [onSelect]);
  const inspect = useCallback((node: GraphNode) => { clock?.pause(); select.current(node); }, [clock]);
  const manual = useRef(false);
  const motion = useTraceClockState(clock);
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
        data: { entity, inspect: (n: GraphNode) => select.current(n) }, ariaLabel: `${entity.label}, ${entity.type}`, draggable: false };
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
  }, [graph]);

  // Selection changes styling only; layout and the React Flow viewport stay intact.
  const highlighted = useMemo(() => {
    const current = trace?.sequence.steps[trace.index];
    const completed = new Set(trace?.sequence.steps.slice(0, trace.index).map(s => s.edge_id));
    const neighbors = new Set([selectedId]);
    graph.edges.forEach(e => { if (e.source === selectedId) neighbors.add(e.target); if (e.target === selectedId) neighbors.add(e.source); });
    return {
      nodes: nodes.map(node => ({ ...node, selected: !trace && node.id === selectedId,
        data: { ...node.data, inspect, cinematic: !!trace, clock: clock ?? undefined, arriving: current?.traversal_to === node.id },
        className: traceNodeIds.length ? traceNodeIds.includes(node.id) ? `trace-node ${current?.traversal_from === node.id ? 'trace-origin' : 'trace-destination'}` : '' : selectedId && neighbors.has(node.id) ? 'connected-node' : '',
        style: { opacity: traceNodeIds.length ? traceNodeIds.includes(node.id) ? 1 : 0.55 : selectedId ? (!neighbors.has(node.id) ? 0.75 : 1) : emphasizedNodeIds.length && !emphasizedNodeIds.includes(node.id) ? 0.65 : 1 } })),
      edges: edges.map(edge => {
        const connected = highlightedEdgeIds.length ? highlightedEdgeIds.includes(edge.id) : edge.source === selectedId || edge.target === selectedId;
        return { ...edge, label: traceRelationshipLabel(String(edge.label)),
          data: { clock: clock ?? undefined, active: current?.edge_id === edge.id, reverse: current?.edge_id === edge.id && current.traversal_from === edge.target },
          className: trace ? connected ? 'trace-edge-active' : completed.has(edge.id) ? 'trace-edge-completed' : 'trace-edge-future' : '',
          style: { ...edge.style, stroke: connected ? '#315d48' : '#7b9181', strokeWidth: connected ? 2.4 : completed.has(edge.id) ? 2 : 1.3, opacity: trace ? connected ? 1 : completed.has(edge.id) ? 0.65 : 0.3 : selectedId && !connected ? 0.55 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: connected ? '#315d48' : '#7b9181' } };
      }),
    };
  }, [nodes, edges, graph.edges, selectedId, highlightedEdgeIds, emphasizedNodeIds, traceNodeIds, trace, clock, inspect]);

  if (!graph.nodes.length) return <div className="graph-empty"><GitEmpty />No connected graph evidence was returned.</div>;
  return <div className={`graph-canvas ${expanded ? 'expanded' : ''} ${trace ? 'cinematic-graph' : ''}`} aria-label="Evidence graph" data-playing={motion.playing}>
    {trace && <button className="trace-recenter button small" onClick={() => clock?.recenter()}>Recenter trace</button>}
    <div className="graph-legend" aria-label="Entity types">
      {Array.from(new Set(graph.nodes.map(n => n.type))).map(type =>
        <span className={`type-${type.toLowerCase()}`} key={type}><i />{type}</span>)}
    </div>
    <ReactFlow nodes={highlighted.nodes} edges={highlighted.edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
      minZoom={0.25} maxZoom={1.6} nodesConnectable={false} edgesFocusable={false}
      onMoveStart={event => { if (event) manual.current = true; }}
      onNodeClick={(_event, node) => inspect(node.data.entity)}>
      <InitialFit visible={visible} fitNodeIds={fitNodeIds} graphKey={graph.nodes.map(n => n.id).join('|')} clock={clock} manual={manual} />
      <Background color="#dce4da" gap={22} size={1} />
      {!trace && <FitGraph manual={manual} />}
      <Controls showInteractive={false} onZoomIn={() => { manual.current = true; }} onZoomOut={() => { manual.current = true; }} onFitView={() => { manual.current = true; }} />
      {expanded && !trace && <MiniMap pannable zoomable nodeColor="#cedbcd" />}
    </ReactFlow>
    <span className="graph-hint">Scroll to zoom · drag to pan · select a node to inspect</span>
  </div>;
}

function GitEmpty() { return <EntityIcon type="Relationship" size={32} />; }
