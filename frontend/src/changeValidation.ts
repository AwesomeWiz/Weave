import type { ChangeBriefData, ChangeEvidenceReference, ChangeInput, ChangeTool, QueryResponse } from './types';
import { validTracePlayback } from './traceValidation';

const tools: ChangeTool[] = ['decision_trace', 'impact_analysis', 'find_expert', 'find_stale_knowledge'];
const publicNames = { decision_trace: 'trace_decision', impact_analysis: 'impact_analysis', find_expert: 'find_expert', find_stale_knowledge: 'find_stale_knowledge' };
const record = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === 'string';
const strings = (v: unknown, max = 200): v is string[] => Array.isArray(v) && v.length <= max && v.every(text);
const ids = (v: unknown, max = 200): v is string[] => strings(v, max) && v.every(s => s.length > 0) && new Set(v).size === v.length;
const status = (v: unknown) => ['supported', 'partially_supported', 'insufficient_evidence'].includes(String(v));
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const time = (v: unknown): number => text(v) && /(?:Z|[+-]\d\d:\d\d)$/.test(v) ? Date.parse(v) : NaN;
const list = (v: unknown, max: number): v is unknown[] => Array.isArray(v) && v.length <= max;

/** Defense at the display boundary; authoritative proof validation remains in FastAPI. */
export function validChangeData(value: unknown, response: QueryResponse, request: ChangeInput): value is ChangeBriefData {
  if (!record(value) || !record(value.proposed_change) || !record(value.tool_support)
    || !strings(value.limitations) || !record(value.historical_context) || !record(value.impact)) return false;
  const data = value;
  if (response.graph.nodes.length > 80 || response.graph.edges.length > 200 || response.sources.length > 30
    || new TextEncoder().encode(JSON.stringify(data)).length > 160000) return false;
  const support = value.tool_support;
  const nodes = new Map(response.graph.nodes.map(n => [n.id, n]));
  const edges = new Map(response.graph.edges.map(e => [e.id, e]));
  const sources = new Set(response.sources.map(s => s.id));
  const nodeCopy = (v: unknown): v is { id: string } => record(v) && text(v.id) && nodes.has(v.id) && same(v, nodes.get(v.id));
  const member = (tool: ChangeTool, field: string, id: string) => {
    const state = support[tool];
    return record(state) && state.state === 'validated' && record(state.evidence)
      && Array.isArray(state.evidence[field]) && state.evidence[field].includes(id);
  };
  function ref(v: unknown, local = true): v is ChangeEvidenceReference {
    if (!record(v) || !tools.includes(v.tool as ChangeTool) || !ids(v.node_ids, 80) || !ids(v.edge_ids, 200)
      || !ids(v.source_ids, 30) || !list(v.relationship_paths, 200)
      || !v.node_ids.every(id => nodes.has(id)) || !v.source_ids.every(id => sources.has(id)
        && response.sources.some(s => s.id === id && [s.id, ...s.entity_ids].some(n => (v.node_ids as string[]).includes(n))))
      || !v.edge_ids.every(id => { const e = edges.get(id); return e && (v.node_ids as string[]).includes(e.source) && (v.node_ids as string[]).includes(e.target); })
      || !v.relationship_paths.every(p => ids(p) && p.length > 0 && p.every(id => (v.edge_ids as string[]).includes(id)))) return false;
    return !local || ['node_ids', 'edge_ids', 'source_ids'].every(field => (v[field] as string[]).every(id => member(v.tool as ChangeTool, field, id)));
  }
  function refs(v: unknown, tool?: ChangeTool): v is ChangeEvidenceReference[] {
    return list(v, 4) && v.length > 0 && v.every(r => ref(r) && r.node_ids.length > 0
      && (r.edge_ids.length > 0 || r.source_ids.length > 0) && (!tool || r.tool === tool));
  }
  function path(v: unknown, tool: ChangeTool, max = 3): v is { source: string; type: string; target: string }[] {
    return list(v, max) && v.length > 0 && v.every(p => record(p) && text(p.source) && text(p.target)
      && text(p.type) && member(tool, 'node_ids', p.source) && member(tool, 'node_ids', p.target)
      && response.graph.edges.some(e => e.source === p.source && e.type === p.type && e.target === p.target && member(tool, 'edge_ids', e.id)));
  }
  const citations = (v: unknown, tool: ChangeTool): v is string[] => ids(v, 30) && v.every(id => sources.has(id) && member(tool, 'source_ids', id));
  const quoted = (summary: unknown, allowed: string[]) => text(summary)
    && [...summary.matchAll(/\[([^\]]+)\]/g)].every(match => allowed.includes(match[1]));

  for (const [tool, item] of Object.entries(support)) {
    if (!tools.includes(tool as ChangeTool) || !record(item) || !status(item.support_status)
      || !['validated', 'unavailable', 'invalid', 'unregistered'].includes(String(item.state))
      || !ref(item.evidence, false) || item.evidence.tool !== tool) return false;
    if (item.state !== 'validated' && (item.support_status !== 'insufficient_evidence'
      || item.evidence.node_ids.length || item.evidence.edge_ids.length || item.evidence.source_ids.length || item.evidence.relationship_paths.length)) return false;
  }
  const validated = Object.entries(support).filter(([, v]) => record(v) && v.state === 'validated').map(([t]) => publicNames[t as ChangeTool]);
  if (!same([...response.tools_used].sort(), validated.sort()) || (response.support_status === 'supported'
    && Object.values(support).some(v => !record(v) || v.state !== 'validated' || v.support_status !== 'supported'))) return false;
  const proposed = value.proposed_change;
  if (proposed.requested_target !== request.target.trim() || proposed.requested_change !== request.change.trim()
    || !['remove_technology', 'unsupported'].includes(String(proposed.intent))
    || !['resolved', 'unsupported', 'unresolved', 'ambiguous', 'inconsistent'].includes(String(proposed.resolution))
    || !(proposed.limitation === null || text(proposed.limitation))
    || !(proposed.service === null || nodeCopy(proposed.service)) || !(proposed.technology === null || nodeCopy(proposed.technology))) return false;
  const service = record(proposed.service) && text(proposed.service.id) ? proposed.service.id : null;
  const technology = record(proposed.technology) && text(proposed.technology.id) ? proposed.technology.id : null;
  if (proposed.resolution === 'resolved' && (proposed.intent !== 'remove_technology' || !service || !technology
    || nodes.get(service)?.type !== 'Service' || nodes.get(technology)?.type !== 'Technology'
    || !response.graph.edges.some(e => e.source === service && e.type === 'USES' && e.target === technology
      && tools.some(t => member(t, 'edge_ids', e.id) && member(t, 'node_ids', e.source) && member(t, 'node_ids', e.target))))) return false;
  if (proposed.resolution !== 'resolved' && response.support_status !== 'insufficient_evidence') return false;
  const history = value.historical_context;
  if (!status(history.support_status) || !text(history.summary) || !ids(history.decision_ids, 30)
    || !history.decision_ids.every(id => nodes.get(id)?.type === 'Decision' && member('decision_trace', 'node_ids', id))
    || !(history.evidence === null || ref(history.evidence) && history.evidence.tool === 'decision_trace')
    || !quoted(history.summary, ref(history.evidence) ? history.evidence.source_ids : [])) return false;
  if (ref(history.evidence) ? !record(support.decision_trace) || history.support_status !== support.decision_trace.support_status
    : history.support_status !== 'insufficient_evidence' || history.decision_ids.length > 0) return false;
  if (history.relationship_paths !== undefined) {
    const names = new Set<string>();
    if (!list(history.relationship_paths, 80) || !history.relationship_paths.every(p => {
      if (!record(p) || Object.keys(p).some(k => !['id', 'steps'].includes(k))
        || !text(p.id) || !p.id.length || p.id.length > 128 || names.has(p.id)
        || !ref(history.evidence) || !path(p.steps, 'decision_trace', 10)
        || !p.steps.every((s, i, steps) => Object.keys(s).every(k => ['source', 'type', 'target'].includes(k))
          && (!i || steps[i - 1].target === s.source))) return false;
      names.add(p.id);
      const evidence = history.evidence;
      const steps = p.steps;
      // Membership in the merged graph alone is insufficient. Require this
      // exact sequence in the historical capability's returned edge-ID proof.
      return evidence.relationship_paths.some(sequence => sequence.length === steps.length && sequence.every((id, i) => {
        const edge = edges.get(id); const step = steps[i];
        return evidence.edge_ids.includes(id) && !!edge && edge.source === step.source && edge.type === step.type && edge.target === step.target;
      }));
    })) return false;
  }

  const impact = value.impact;
  if (!status(impact.support_status) || !Number.isInteger(impact.max_depth) || Number(impact.max_depth) < 1 || Number(impact.max_depth) > 3
    || !(impact.entity === null || nodeCopy(impact.entity) && impact.entity.id === technology)) return false;
  function related(v: unknown, kind: string): boolean {
    return list(v, 160) && v.every(r => record(r) && text(r.id) && nodes.get(r.id)?.type === kind && text(r.title)
      && same(r.properties, nodes.get(r.id)?.properties) && text(r.service_id) && member('impact_analysis', 'node_ids', r.id)
      && (response.graph.edges.some(e => e.source === r.id && e.type === 'AFFECTS' && e.target === r.service_id && member('impact_analysis', 'edge_ids', e.id))
        || kind === 'Incident' && response.graph.edges.some(e => e.source === r.id && e.type === 'LED_TO' && member('impact_analysis', 'edge_ids', e.id)
          && response.graph.edges.some(a => a.source === e.target && a.type === 'AFFECTS' && a.target === r.service_id && member('impact_analysis', 'edge_ids', a.id)))));
  }
  const seenServices = new Set<string>();
  function impacts(v: unknown, kind: string): boolean {
    return list(v, 60) && v.every(f => {
      if (!record(f) || !text(f.service_id) || seenServices.has(f.service_id) || nodes.get(f.service_id)?.type !== 'Service'
        || !same(f.service, nodes.get(f.service_id)?.properties) || f.impact_type !== kind || !Number.isInteger(f.impact_depth)
        || Number(f.impact_depth) < 1 || Number(f.impact_depth) > Number(impact.max_depth) || (f.impact_depth === 1) !== (kind === 'direct')
        || !ids(f.path, 4) || f.path.length !== Number(f.impact_depth) + 1 || f.path[0] !== technology || f.path[1] !== service || f.path.at(-1) !== f.service_id
        || !path(f.path_edges, 'impact_analysis') || f.path_edges.length !== f.impact_depth
        || !f.path_edges.every((p, i) => p.source === (f.path as string[])[i + 1] && p.target === (f.path as string[])[i]
          && p.type === (i === 0 ? 'USES' : 'DEPENDS_ON'))
        || !list(f.owners, 80) || !f.owners.every(o => record(o) && text(o.id) && text(o.name) && nodes.get(o.id)?.properties.name === o.name
          && response.graph.edges.some(e => e.source === o.id && e.type === 'OWNS' && e.target === f.service_id && member('impact_analysis', 'edge_ids', e.id)))
        || !related(f.related_issues, 'Issue') || !related(f.related_incidents, 'Incident') || !citations(f.source_ids, 'impact_analysis')) return false;
      seenServices.add(f.service_id); return true;
    });
  }
  if (!impacts(impact.direct_impact, 'direct') || !impacts(impact.indirect_impact, 'indirect')
    || !related(impact.related_issues, 'Issue') || !related(impact.related_incidents, 'Incident')) return false;

  const categories = ['team_ownership', 'decision_approval', 'decision_participation', 'commit_authorship', 'issue_assignment', 'discussion_contribution'];
  function proofs(v: unknown, person: string): boolean {
    return list(v, 100) && v.every(p => {
      if (!record(p) || !categories.includes(String(p.category)) || !text(p.entity_id) || nodes.get(p.entity_id)?.type !== p.entity_type
        || !path(p.path, 'find_expert', 2) || !citations(p.source_ids, 'find_expert')) return false;
      const steps = p.path;
      if (p.category === 'team_ownership') return !p.source_ids.length && steps.length === 2 && steps[0].source === person
        && steps[0].type === 'MEMBER_OF' && nodes.get(steps[0].target)?.type === 'Team' && steps[1].source === steps[0].target && steps[1].type === 'OWNS' && steps[1].target === p.entity_id;
      const relationship = { decision_approval: 'APPROVED', decision_participation: 'PARTICIPATED_IN', commit_authorship: 'AUTHORED', issue_assignment: 'ASSIGNED_TO', discussion_contribution: 'WROTE' }[p.category as string];
      return steps.length === 1 && steps[0].type === relationship && (p.category === 'issue_assignment'
        ? steps[0].source === p.entity_id && steps[0].target === person : steps[0].source === person && steps[0].target === p.entity_id);
    });
  }
  const seenPeople = new Set<string>();
  let previousScore = Infinity, previousId = '';
  if (!list(data.reviewers, 10) || !data.reviewers.every(p => {
    if (!record(p) || !record(p.person) || !text(p.person.id) || seenPeople.has(p.person.id) || nodes.get(p.person.id)?.type !== 'Person'
      || p.person.name !== nodes.get(p.person.id)?.properties.name || !(p.person.role === null || text(p.person.role))
      || p.person.role !== (nodes.get(p.person.id)?.properties.role ?? null)
      || !Number.isInteger(p.score) || Number(p.score) < 1 || Number(p.score) > previousScore || Number(p.score) === previousScore && p.person.id < previousId
      || !strings(p.ranking_reasons, 100) || !proofs(p.evidence, p.person.id) || !(p.evidence as unknown[]).length
      || !proofs(p.ownership, p.person.id) || !proofs(p.historical_contributions, p.person.id)
      || !['team_membership_with_team_owned_service', 'no_current_ownership_evidence'].includes(String(p.ownership_classification))) return false;
    const evidence = p.evidence as Record<string, unknown>[];
    if (!same(p.ownership, evidence.filter(e => e.category === 'team_ownership')) || !same(p.historical_contributions, evidence.filter(e => e.category !== 'team_ownership'))
      || (p.ownership as unknown[]).length > 0 !== (p.ownership_classification === 'team_membership_with_team_owned_service')) return false;
    seenPeople.add(p.person.id); previousScore = Number(p.score); previousId = p.person.id; return true;
  })) return false;
  if (!list(data.risks, 30) || !data.risks.every(r => {
    if (!record(r) || !['KNOWN_FACT', 'INFERRED_RISK', 'RECOMMENDATION'].includes(String(r.classification))
      || !text(r.description) || !text(r.uncertainty) || !refs(r.evidence) || !ids(r.affected_entity_ids, 80)) return false;
    const evidence = r.evidence;
    return r.affected_entity_ids.every(id => evidence.some(ref => ref.node_ids.includes(id)))
      && (r.classification !== 'INFERRED_RISK' || record(support.decision_trace) && support.decision_trace.support_status === 'supported'
        && evidence.some(ref => ref.tool === 'decision_trace' && ref.source_ids.length > 0));
  })) return false;
  if (!list(data.validation_steps, 30) || !data.validation_steps.every(s => record(s) && s.classification === 'RECOMMENDATION'
    && s.performed === false && text(s.description) && refs(s.evidence))) return false;

  function documentPath(v: unknown, docId: string): boolean {
    if (!path(v, 'find_stale_knowledge', 2)) return false;
    return v.length === 1 ? v[0].source === docId && v[0].type === 'DESCRIBES' && v[0].target === service
      : nodes.get(v[0].source)?.type === 'Decision' && v[0].type === 'DOCUMENTED_IN' && v[0].target === docId
        && v[1].source === v[0].source && v[1].type === 'AFFECTS' && v[1].target === service;
  }
  const seenCurrent = new Set<string>();
  if (!list(data.current_freshness_findings, 50) || !data.current_freshness_findings.every(f => {
    if (!record(f) || !text(f.document_id) || nodes.get(f.document_id)?.type !== 'Document' || !nodeCopy(f.document)
      || seenCurrent.has(f.document_id) || f.document.id !== f.document_id || f.affected_entity_id !== service
      || f.reason !== 'Later graph-linked changes affect the same service; review may be warranted.'
      || f.updated_at !== nodes.get(f.document_id)?.properties.updated_at || !Number.isFinite(time(f.updated_at))
      || !documentPath(f.document_path, f.document_id) || !citations(f.source_ids, 'find_stale_knowledge') || f.source_ids.some(id => id !== f.document_id)
      || !list(f.triggers, 150) || !f.triggers.length) return false;
    seenCurrent.add(f.document_id);
    const seen = new Set<string>();
    return f.triggers.every(t => {
      if (!record(t) || !text(t.id) || seen.has(t.id) || !path(t.path, 'find_stale_knowledge', 1) || t.path[0].source !== t.id
        || t.path[0].target !== service || t.affected_entity_id !== service || !Number.isFinite(time(t.timestamp))
        || time(t.timestamp) <= time(f.updated_at) || !citations(t.source_ids, 'find_stale_knowledge')) return false;
      const node = nodes.get(t.id);
      const valid = t.type === 'decision' ? node?.type === 'Decision' && node.properties.status === 'accepted' && t.timestamp === node.properties.decided_at && t.path[0].type === 'AFFECTS'
        : t.type === 'commit' ? node?.type === 'Commit' && node.properties.architecture_change === true && t.timestamp === node.properties.timestamp && t.path[0].type === 'CHANGES'
          : t.type === 'incident' && node?.type === 'Incident' && t.timestamp === node.properties.started_at && t.path[0].type === 'AFFECTS';
      if (!valid || (t.type === 'commit' ? t.source_ids.some(id => id !== t.id) : t.source_ids.length > 0)) return false;
      seen.add(t.id); return true;
    });
  })) return false;
  const seenFuture = new Set<string>();
  if (!list(data.documents_to_review_if_change_proceeds, 50) || !data.documents_to_review_if_change_proceeds.every(d => {
    if (!record(d) || !nodeCopy(d.document) || nodes.get(d.document.id)?.type !== 'Document'
      || seenFuture.has(d.document.id) || d.condition !== 'if_change_approved_and_implemented' || !text(d.reason) || !refs(d.evidence)) return false;
    const doc = d.document;
    seenFuture.add(doc.id);
    return d.evidence.some(ref => ref.node_ids.includes(doc.id) && ref.edge_ids.some(id => {
      const e = edges.get(id);
      if (!e) return false;
      return e.source === doc.id && e.type === 'DESCRIBES' && e.target === service
        || e.target === doc.id && e.type === 'DOCUMENTED_IN' && ref.edge_ids.some(a => {
          const affects = edges.get(a); return affects && affects.source === e.source && affects.type === 'AFFECTS' && affects.target === service;
        });
    }));
  })) return false;
  return quoted(response.answer, [...sources]) && validTracePlayback(data.trace_playback, data as unknown as ChangeBriefData, response);
}
