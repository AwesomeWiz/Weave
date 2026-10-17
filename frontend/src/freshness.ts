import type { FreshnessInput, FreshnessResponse, QueryResponse } from './types';

export const FRESHNESS_QUESTION = 'Which documents about Payment Service need review?';

export function routeFreshnessQuestion(question: string): FreshnessInput | null {
  if (/\band\s+(what|why|which|who|how|are|is|tell|show|find|check)\b|[;?].+\S|,\s*who\b/i.test(question)) return null;
  const patterns = [
    /^(?:is|are) (?:the )?(.+?) (?:documentation|documents|docs) (?:stale|outdated|up.to.date|still current)$/i,
    /^which (?:documents|docs) (?:about|for) (.+?) need review$/i,
    /^(?:check |show )?(?:knowledge )?freshness (?:for|of) (.+)$/i,
  ];
  for (const pattern of patterns) {
    const entity = question.trim().replace(/\?$/, '').match(pattern)?.[1]?.trim();
    if (entity && !/\b(and|or|our|this|that|it)\b/i.test(entity)
      && /^(service:[a-z0-9]+(?:-[a-z0-9]+)*|[A-Za-z][A-Za-z0-9 -]* Service)$/i.test(entity)) return { entity };
  }
  return null;
}

export function isFreshnessResponse(result: QueryResponse): result is FreshnessResponse {
  return result.tools_used.length === 1 && result.tools_used[0] === 'find_stale_knowledge' && 'data' in result;
}
