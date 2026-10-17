import type { ImpactInput, ImpactResponse, QueryResponse } from './types';

export const IMPACT_QUESTION = 'What would be affected if Payment Service changed?';
export const IMPACT_TARGETS = [
  ['service:payment-service', 'Payment Service'], ['tech:redis', 'Redis'],
  ['service:checkout-service', 'Checkout Service'], ['service:order-service', 'Order Service'],
  ['tech:postgresql', 'PostgreSQL'],
] as const;

// UI endpoint selection only; the backend independently resolves /api/query.
// These documented aliases resolve identifiers, never evidence or dependencies.
export function routeImpactQuestion(question: string): ImpactInput | null {
  const text = question.toLowerCase();
  // Compound questions belong to the backend planner, never this single-tool shortcut.
  if (/\band\s+(what|why|which|who|how|are|is|tell|show|find|check)\b|[;?].+\S/.test(text)
    || /\bwhat (?:has )?changed\b|\bchanges (?:to|in)\b/.test(text)
    || /\b(why|decision|rationale|introduced|led to|evidence|owns|owner|chose|chosen|expert|experts|freshness|stale|outdated|up to date)\b/.test(text)
    || !/\b(affect\w*|impact\w*|depends on|depend on|break\w*|removed?|changed?)\b/.test(text)) return null;
  const aliases: [RegExp, string][] = [
    [/\bpayments?[ -]service\b/, 'service:payment-service'], [/\bcheckout[ -]service\b/, 'service:checkout-service'],
    [/\border[ -]service\b/, 'service:order-service'], [/\bredis\b/, 'tech:redis'], [/\bpostgres(?:ql)?\b/, 'tech:postgresql'],
  ];
  const targets = aliases.filter(([pattern]) => pattern.test(text)).map(([, id]) => id);
  const namedServices = text.match(/\b[a-z0-9]+[ -]service\b/g) ?? [];
  if (namedServices.some(name => !/^(payments?|checkout|order)[ -]service$/.test(name)
    && !['what service', 'which service', 'the service', 'this service'].includes(name))) return null;
  const dependency = /\bdepends? on\b/.exec(text);
  if (!/\b(affect\w*|impact\w*|break\w*|removed?|changed?)\b/.test(text)
    && (!dependency || !aliases.some(([pattern]) => pattern.test(text.slice(dependency.index + dependency[0].length))))) return null;
  return targets.length === 1 ? { entity_id: targets[0], max_depth: 2 } : null;
}

export function isImpactResponse(result: QueryResponse): result is ImpactResponse {
  return result.tools_used.includes('impact_analysis') && 'data' in result;
}
