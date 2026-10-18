import { useState } from 'react';
import type { ReactNode } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Node, ReactFlowProps } from '@xyflow/react';
import EvidenceGraph from './components/EvidenceGraph';
import Inspector from './components/Inspector';
import type { EvidenceGraph as Graph, GraphNode, QueryResponse } from './types';

type FlowNode = Node<{ entity: GraphNode; inspect: (node: GraphNode) => void }>;
const flow = vi.hoisted(() => ({ nodes: [] as FlowNode[], edges: [] as { id: string; source: string; target: string }[] }));
vi.mock('@xyflow/react', async original => ({ ...await original<typeof import('@xyflow/react')>(),
  ReactFlow: ({ nodes = [], edges = [], nodeTypes, children }: ReactFlowProps<FlowNode>) => {
    flow.nodes = nodes; flow.edges = edges;
    return <div>{nodes.map(node => {
      const Renderer = nodeTypes![node.type!];
      return <Renderer key={node.id} id={node.id} type={node.type!} data={node.data}
        selected={!!node.selected} dragging={false} draggable={false} selectable deletable={false}
        isConnectable={false} zIndex={0} positionAbsoluteX={node.position.x} positionAbsoluteY={node.position.y} />;
    })}{children as ReactNode}</div>;
  },
  Handle: ({ id, type }: { id: string; type: string }) => <span data-testid="node-handle" data-id={id} data-type={type} />,
  Background: () => null, Controls: () => null, MiniMap: () => null,
  useNodesInitialized: () => false,
  useReactFlow: () => ({ fitView: vi.fn(async () => true), getViewport: () => ({ x: 0, y: 0, zoom: 1 }), setViewport: vi.fn() }),
  useStore: (select: (state: { width: number; height: number }) => unknown) => select({ width: 800, height: 540 }),
}));
afterEach(cleanup);

const categories = ['Service', 'Technology', 'Document', 'Decision', 'Person', 'Team', 'Issue',
  'Incident', 'Message', 'Commit', 'Repository', 'Project', 'Relationship', 'Chunk', 'FutureCategory'];
const chunk: GraphNode = { id: 'chunk:doc:ADR-7:0', type: 'Chunk', label: 'ADR-7: Redis Caching for Payment Service',
  properties: { source_id: 'doc:ADR-7', chunk_index: 0, text: 'Original retrieved excerpt.', provenance: { source_type: 'Document' } } };
const graph: Graph = {
  nodes: categories.map(type => type === 'Chunk' ? chunk : {
    id: type === 'Document' ? 'doc:ADR-7' : `test:${type}`, type, label: `${type} label`, properties: { original_type: type },
  }),
  edges: [{ id: 'chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7', source: chunk.id, type: 'FROM_DOCUMENT', target: 'doc:ADR-7', properties: {} }],
};

it('uses the registered card renderer and connection handles for every category, including chunks and unknown types', () => {
  const { container } = render(<EvidenceGraph graph={graph} onSelect={vi.fn()} />);
  expect(container.querySelectorAll('.entity-node')).toHaveLength(categories.length);
  for (const node of graph.nodes) {
    const card = container.querySelector(`.entity-node.type-${node.type.toLowerCase()}`)!;
    expect(card).not.toBeNull();
    expect(card).toHaveClass(`type-${node.type.toLowerCase()}`);
    expect(card.querySelectorAll('[data-testid="node-handle"]')).toHaveLength(8);
    expect(new Set(Array.from(card.querySelectorAll('[data-testid="node-handle"]')).map(h => h.getAttribute('data-id'))).size).toBe(8);
    if (node.type !== 'FutureCategory') expect(card.querySelector('.lucide-circle-help')).toBeNull();
  }
  expect(container.querySelector('.type-chunk .lucide-file-text')).not.toBeNull();
});

it('passes the original chunk and provenance to the Inspector without altering stored IDs, types or edge directions', () => {
  const before = structuredClone(graph);
  const selected = vi.fn();
  const result: QueryResponse = { answer: 'Offline rendering sample', support_status: 'partially_supported',
    tools_used: ['trace_decision'], graph, sources: [],
    metadata: { graph_mode: 'falkordb', generation: 'deterministic', latency_ms: 1, warnings: [] } };
  function Harness() {
    const [node, setNode] = useState<GraphNode | null>(null);
    return <><EvidenceGraph graph={graph} selectedId={node?.id} onSelect={value => { selected(value); setNode(value); }} />
      <Inspector result={result} selectedNode={node} selectedSource={null} health={null} healthError={false}
        onNode={setNode} onSource={vi.fn()} onClose={() => setNode(null)} onRefresh={vi.fn()} /></>;
  }
  render(<Harness />);
  fireEvent.click(screen.getByRole('button', { name: `Inspect ${chunk.label}` }));
  expect(selected).toHaveBeenCalledWith(chunk);
  expect(selected.mock.calls[0][0]).toBe(chunk);
  expect(screen.getByRole('complementary', { name: 'Entity inspector' })).toHaveTextContent(chunk.id);
  expect(screen.getByRole('complementary', { name: 'Entity inspector' })).toHaveTextContent('Original retrieved excerpt.');
  expect(flow.nodes.find(n => n.id === chunk.id)!.data.entity).toBe(chunk);
  expect(flow.edges[0]).toMatchObject({ id: graph.edges[0].id, source: chunk.id, target: 'doc:ADR-7' });
  expect(graph).toEqual(before);
});
