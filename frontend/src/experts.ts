import type { ExpertInput, ExpertResponse, QueryResponse } from './types';

export const EXPERT_QUESTION = 'Who knows Payment Service?';

export function routeExpertQuestion(question: string): ExpertInput | null {
  // Mixed intents stay with the backend planner, including the showcase query.
  if (/\band\s+(what|why|which|who|how|are|is|tell|show|find|check)\b|[;?].+\S|,\s*who\b/i.test(question)) return null;
  return /\b(expert|experts|who knows|who worked on|who can explain|who approved|who made (?:the|this) decision)\b/i.test(question)
    ? { query: question.trim(), limit: 5 } : null;
}

export function isExpertResponse(result: QueryResponse): result is ExpertResponse {
  return result.tools_used.length === 1 && result.tools_used[0] === 'find_expert' && 'data' in result;
}
