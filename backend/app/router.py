import re

from .models import ImpactInput, TraceInput


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
