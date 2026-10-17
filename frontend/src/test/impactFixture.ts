import type { ImpactFinding, ImpactResponse } from '../types';

const payment = 'service:payment-service', checkout = 'service:checkout-service', order = 'service:order-service';
const directEdge = { source: checkout, type: 'DEPENDS_ON' as const, target: payment };
const indirectEdge = { source: order, type: 'DEPENDS_ON' as const, target: checkout };
const node = (id: string, label: string) => ({ id, label, type: 'Service', properties: { id, name: label } });
const nodes = [node(payment, 'Payment Service'), node(checkout, 'Checkout Service'), node(order, 'Order Service')];
const finding = (index: number): ImpactFinding => ({
  service_id: nodes[index].id, service: nodes[index].properties, impact_depth: index,
  impact_type: index === 1 ? 'direct' : 'indirect', path: nodes.slice(0, index + 1).map(n => n.id),
  path_edges: index === 1 ? [directEdge] : [directEdge, indirectEdge],
  owners: [], related_issues: [], related_incidents: [], source_ids: [],
});
export const impactFixture: ImpactResponse = {
  answer: 'Offline test-only structural impact.', support_status: 'partially_supported', tools_used: ['impact_analysis'],
  sources: [], graph: { nodes, edges: [directEdge, indirectEdge].map((edge, i) => ({ ...edge, id: `edge-${i}`, properties: {} })) },
  metadata: { graph_mode: 'fixture', generation: 'deterministic', latency_ms: 1, warnings: ['Structural evidence only.'] },
  data: { entity: nodes[0], direct_impact: [finding(1)], indirect_impact: [finding(2)], related_issues: [], related_incidents: [] },
};
