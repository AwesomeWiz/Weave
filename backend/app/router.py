import re

from .models import TraceInput


def route_question(question: str) -> TraceInput | None:
    """Bounded Phase 1 intent rules. No guessed entities or model-selected tools."""
    text = question.casefold()
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
