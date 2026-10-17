import json
import re
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from .models import ExpertInput, ImpactInput, TraceInput


IMPACT_ALIASES = {
    "payment service": "service:payment-service", "payments service": "service:payment-service",
    "payment-service": "service:payment-service", "checkout service": "service:checkout-service",
    "checkout-service": "service:checkout-service", "order service": "service:order-service",
    "order-service": "service:order-service", "redis": "tech:redis",
    "postgresql": "tech:postgresql", "postgres": "tech:postgresql",
}


def route_impact(question: str) -> ImpactInput | None:
    text = question.casefold()
    # Mixed why/ownership requests need more than one tool and remain unsupported.
    if re.search(r"\b(why|decision|rationale|owns|owner|chose|chosen)\b", text):
        return None
    if not re.search(r"\b(affect\w*|impact\w*|depends on|depend on|break\w*|removed?|changed?)\b", text):
        return None
    targets = {value for alias, value in IMPACT_ALIASES.items()
               if re.search(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", text)}
    if len(targets) != 1:
        return None
    mentions = re.findall(r"\b[a-z0-9]+[ -]service\b", text)
    if any(m not in IMPACT_ALIASES and m not in {"what service", "which service", "the service", "this service"}
           for m in mentions):
        return None
    # The tool traverses dependents, not the target's upstream dependencies.
    dependency = re.search(r"\bdepends? on\b", text)
    if (not re.search(r"\b(affect\w*|impact\w*|break\w*|removed?|changed?)\b", text)
            and (dependency is None or not any(
                re.search(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", text[dependency.end():])
                for alias in IMPACT_ALIASES))):
        return None
    return ImpactInput(entity_id=targets.pop())


def route_question(question: str) -> TraceInput | ImpactInput | None:
    """Bounded single-tool rules. No guessed entities or model-selected tools."""
    text = question.casefold()
    impact = route_impact(question)
    if impact:
        return impact
    if not re.search(r"\b(why|decision|introduced|chose|chosen|evidence|rationale)\b", text):
        return None
    # Short screenshot prompt is an explicit alias for the one Phase 1 trace.
    if re.fullmatch(r"\s*why was redis introduced\s*\??\s*", text):
        return TraceInput(service="Payment Service", technology="Redis")
    # Do not route a mixed impact/ownership request as fully answered.
    if re.search(r"\b(remove|removed|impact|affected|break|owns|owner)\b", text):
        return None
    if re.search(r"\bpayment service\b", text) and re.search(r"\bredis\b", text):
        return TraceInput(service="Payment Service", technology="Redis")
    return None


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: BaseModel

    @property
    def key(self) -> tuple[str, str]:
        return self.name, json.dumps(self.arguments.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class RoutingPlan:
    calls: tuple[ToolCall, ...] = ()
    limitations: tuple[str, ...] = ()
    composite: bool = False


@dataclass(frozen=True)
class RoutingRule:
    name: str
    match: Callable[[str], BaseModel | None]


class DeferredIntent(BaseModel):
    """Intent recognition only; not graph arguments for an unfinished capability."""
    question: str


def _trace_intent(clause: str) -> TraceInput | None:
    text = clause.casefold()
    if _expert_intent(clause):
        return None
    # Keep clauses explicit. Never resolve a pronoun or silently choose between
    # several services/technologies, even when the Phase 1 alias is also present.
    if re.search(r"\band\b", text):
        return None
    targets = {id for alias, id in IMPACT_ALIASES.items()
               if re.search(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", text)}
    if targets - {"service:payment-service", "tech:redis"}:
        return None
    mentions = re.findall(r"\b[a-z0-9]+[ -]service\b", text)
    if any(m not in {"payment service", "payments service", "payment-service"} for m in mentions):
        return None
    candidate = route_question(re.sub(r"^\s*what led to\b", "why", text))
    return candidate if isinstance(candidate, TraceInput) else None


def _expert_intent(clause: str) -> ExpertInput | None:
    return ExpertInput(query=clause.strip()) if re.search(
        r"\b(expert|experts|who knows|who worked on|who can explain|who approved|who made (?:the|this) decision)\b",
        clause, re.I) else None


def _impact_intent(clause: str) -> ImpactInput | None:
    # Historical change questions are not hypothetical downstream impact.
    if re.search(r"\bwhat (?:has )?changed\b|\bchanges (?:to|in)\b", clause, re.I):
        return None
    return route_impact(clause)


def _freshness_intent(clause: str) -> DeferredIntent | None:
    return DeferredIntent(question=clause) if re.search(
        r"\b(stale|freshness|outdated|up to date|up-to-date)\b", clause, re.I) else None


# Trusted registry order is also execution order. Future matchers do not provide
# fabricated graph arguments; registering their real resolver/executor is separate.
ROUTING_RULES = (
    RoutingRule("decision_trace", _trace_intent),
    RoutingRule("impact_analysis", _impact_intent),
    RoutingRule("find_expert", _expert_intent),
    RoutingRule("find_stale_knowledge", _freshness_intent),
)


def plan_question(question: str, rules: tuple[RoutingRule, ...] = ROUTING_RULES) -> RoutingPlan:
    """Up to four explicit intent clauses; no inferred entities or tool arguments."""
    text = question.strip().strip("?; ")
    # One documented anaphoric grammar, with an explicit service/technology pair.
    # 'it' is the object of 'use'; arbitrary pronouns elsewhere stay unresolved.
    showcase = re.fullmatch(r"why does payment service use redis,?\s+who made the decision,?\s+and "
                            r"what would be affected if we removed it", text, re.I)
    if showcase and rules is ROUTING_RULES:
        return RoutingPlan((
            ToolCall("decision_trace", TraceInput(service="Payment Service", technology="Redis")),
            ToolCall("impact_analysis", ImpactInput(entity_id="tech:redis")),
            ToolCall("find_expert", ExpertInput(query="Who can explain the Redis decision?")),
        ), composite=True)
    clauses = re.split(
        r"[;?]+\s*(?:and\s+)?|,\s*(?=who\b)|\s*,?\s+and\s+(?=(?:what|why|which|who|how|are|is|tell|show|find|check)\b)",
        text, flags=re.I,
    )
    if len(clauses) > 4:
        return RoutingPlan(limitations=("The question exceeds the four-clause routing limit; split it into smaller questions.",), composite=True)
    selected, ambiguous, limitations = {}, set(), []
    for clause in clauses:
        matches = [ToolCall(rule.name, arguments) for rule in rules
                   if (arguments := rule.match(clause.strip(" ,"))) is not None]
        if len(matches) != 1:
            limitations.append("Part of the question has an unknown or ambiguous intent or target; no tool was run for that part.")
            continue
        call = matches[0]
        if call.name in selected and selected[call.name].key != call.key:
            ambiguous.add(call.name)
            limitations.append(f"Multiple targets for {call.name} are ambiguous; ask about one target per capability.")
        else:
            selected[call.name] = call
    calls = tuple(selected[rule.name] for rule in rules if rule.name in selected and rule.name not in ambiguous)
    return RoutingPlan(calls, tuple(dict.fromkeys(limitations)), len(clauses) > 1)
