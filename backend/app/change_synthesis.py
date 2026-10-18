"""Minimal presentation over the validated Change Brief, with no new retrieval.

No raw source excerpts, node properties, URLs, profiles, or user instructions are
sent. All facts/uncertainty are authored by the deterministic Change builder.
"""
import re

from .citations import validate_citations
from .context_v2 import CombinedContext
from .models import ChangeBriefData
from .synthesis import SynthesisBlock, SynthesisPacket

MAX_PACKET_BYTES = 24000
_UNSAFE = re.compile(
    r"https?://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|<[/!]?[A-Za-z]|\]\("
    r"|[\x00-\x08\x0b\x0c\x0e-\x1f]"
    r"|ignore\s+(?:all\s+)?(?:previous|prior|above|instructions)"
    r"|(?:system|assistant|developer)\s*(?:prompt|message|:)"
    r"|(?:api[_ -]?key|authorization|bearer|password|secret[_ -]?token)\s*[:=]",
    re.I,
)


def prepare_change_synthesis(data: ChangeBriefData, context: CombinedContext) -> SynthesisPacket:
    """Called only after _build and its bounded structured/citation validation."""
    if data.proposed_change.resolution != "resolved" or context.status == "insufficient_evidence":
        raise ValueError("No resolved supported proposal to present")
    nodes = {n.id: n for n in context.graph.nodes}
    known = {s.id for s in context.sources}

    def reference(ref):
        p = context.per_tool[ref.tool]
        if (p.state != "validated" or set(ref.node_ids) - set(p.node_ids)
                or set(ref.edge_ids) - set(p.edge_ids) or set(ref.source_ids) - set(p.source_ids)
                or set(ref.source_ids) - known
                or any(set(path) - set(ref.edge_ids) for path in ref.relationship_paths)):
            raise ValueError("Presentation reference outside validated capability")

    for tool, support in data.tool_support.items():
        p = context.per_tool[tool]
        if support.support_status != p.status or support.state != p.state:
            raise ValueError("Presentation support mismatch")
        if p.state == "validated":
            reference(support.evidence)
    history = data.historical_context
    trace = context.per_tool.get("decision_trace")
    if history.relationship_paths != list(trace.ordered_paths if trace and trace.state == "validated" else ()):
        raise ValueError("Historical paths differ from validated Decision Trace provenance")
    if history.evidence:
        reference(history.evidence)
    accepted = [id for id in history.decision_ids if id in nodes and nodes[id].type == "Decision"
                and nodes[id].properties.get("status") == "accepted"]
    historical = f"Historical evidence: {history.support_status.replace('_', ' ')}. "
    historical += ("Retrieved accepted decisions: " + ", ".join(accepted) + ". " if accepted
                   else "No accepted decision established in the retrieved history. ")
    inferred = []
    for risk in data.risks:
        for ref in risk.evidence:
            reference(ref)
        if risk.classification != "INFERRED_RISK":
            continue
        ids = sorted({id for ref in risk.evidence for id in ref.source_ids})
        text = f"INFERRED RISK: {risk.description} {risk.uncertainty} " + " ".join(f"[{id}]" for id in ids)
        validate_citations(text, ids, known, require_every_paragraph=False, allow_empty=True)
        inferred.append(text)
    historical += " ".join(inferred) if inferred else "No historical-rationale risk inference established."

    impacts = data.impact.direct_impact + data.impact.indirect_impact
    stored = " ".join(f"{f.impact_type.capitalize()} impact, depth {f.impact_depth}: " + "; ".join(
        f"{p.source} uses {p.target}" if p.type == "USES" else f"{p.source} depends on {p.target}"
        for p in f.path_edges) + "." for f in impacts)
    stored = ("KNOWN FACT — stored relationships: " + stored if stored else
              "No validated impact paths through Payment Service returned; this does not establish no impact.")
    stored += " Potential impact is not guaranteed failure."
    reviewers = "; ".join(f"{i + 1}. {r.person.name} ({r.person.id}), evidence score {r.score}"
                          for i, r in enumerate(data.reviewers))
    reviewers = ("Evidence-ranked reviewers: " + reviewers + "." if reviewers else
                 "No independently validated reviewer rankings available.")
    reviewers += " Historical expertise and team membership do not establish current personal ownership."
    current = "; ".join(f"{f.document_id} (updated {f.updated_at})" for f in data.current_freshness_findings)
    future = ", ".join(d.document.id for d in data.documents_to_review_if_change_proceeds)
    checks = ("RECOMMENDATION — validation not performed: verify cache-removal behavior and the returned "
              "dependency paths before rollout. This analysis does not approve or execute a change. "
              if data.validation_steps else "No evidence-constrained validation steps available. ")
    checks += ("CURRENT KNOWLEDGE FRESHNESS — review recommended: " + current +
               ". Later graph-linked changes warrant review, not a conclusion that a document is wrong. "
               if current else "No current freshness findings established; documentation is not proven current. ")
    checks += ("FUTURE DOCUMENT REVIEW — only if approved and implemented, review: " + future +
               ". This does not establish current staleness." if future else
               "No documents with validated conditional review associations returned.")

    contents = [
        ("history", "Proposed change and history", historical,
         "Proposed removal of Redis from Payment Service; no change has been executed. " + historical),
        ("impact", "Dependency overview", stored, "For the proposed removal, " + stored),
        ("reviewers", "Review coordination", reviewers, "Coordinate review using the existing evidence ranking. " + reviewers),
        ("checks", "Validation and documentation", checks, "Keep engineering checks and document review separate. " + checks),
    ]
    blocks = [SynthesisBlock(id, title, {"recorded": recorded, "explanation": explanation})
              for id, title, recorded, explanation in contents]
    footer = f"Overall evidence status: {context.status.replace('_', ' ')}. "
    if context.status == "partially_supported":
        footer += "Some evidence is incomplete; presentation cannot resolve those gaps. "
    footer += "Per-tool support: " + "; ".join(
        f"{tool}: {p.support_status} ({p.state})" for tool, p in data.tool_support.items()) + "."
    if data.limitations:
        footer += "\n\nLimitations: " + " ".join(data.limitations)
    cited = frozenset(re.findall(r"\[([^\]]+)\]", " ".join(c[2] + c[3] for c in contents) + footer))
    if cited - known:
        raise ValueError("Unknown presentation citations")
    # Only citation handles and tool-local support are needed alongside the
    # complete server-authorized variants. The mandatory footer is never optional.
    evidence = {"proposal": "Remove Redis from Payment Service", "support_status": context.status,
                "citation_handles": sorted(cited),
                "limitations": list(data.limitations),
                "tool_support": {tool: {"status": p.support_status, "state": p.state}
                                 for tool, p in data.tool_support.items()}}
    packet = SynthesisPacket(evidence, blocks, footer, cited)
    serialized = packet.prompt("Review the proposed removal of Redis from Payment Service.")
    if len(serialized.encode("utf-8")) > MAX_PACKET_BYTES or _UNSAFE.search(serialized):
        raise ValueError("Unsafe or oversized Change presentation packet")
    # Preflight both complete variants before any external request. This also
    # bounds rendered length and catches unsafe footer content locally.
    for variant in ("recorded", "explanation"):
        packet.render({"selections": [{"block_id": b.id, "variant": variant} for b in blocks],
                       "source_ids": sorted(cited)})
    return packet
