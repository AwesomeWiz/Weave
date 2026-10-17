"""Grounded presentation choices, never model-authored company facts.

Citation membership cannot prove arbitrary prose. Instead, the model selects and
orders complete, independently validated sections using server-rendered variants.
"""
import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .citations import validate_citations
from .context import EvidenceContext
from .context_v2 import CombinedContext, ToolEvidence, merge_contexts
from .models import ImpactData


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    block_id: str
    variant: Literal["recorded", "explanation"]


class SynthesisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    selections: list[Selection] = Field(min_length=1, max_length=4)
    source_ids: list[str] = Field(max_length=30)


@dataclass(frozen=True)
class SynthesisBlock:
    id: str
    title: str
    variants: dict[str, str]


@dataclass(frozen=True)
class SynthesisPacket:
    evidence: dict
    blocks: list[SynthesisBlock]
    footer: str
    source_ids: frozenset[str]

    def prompt(self, question: str) -> str:
        text = json.dumps({"question": question, "validated_evidence": self.evidence,
                           "allowed_sections": [b.__dict__ for b in self.blocks]}, ensure_ascii=False)
        if len(text.encode("utf-8")) > 96000:
            raise ValueError("Synthesis input exceeds its bound")
        return text

    def schema(self) -> dict:
        schema = SynthesisPlan.model_json_schema()
        schema["$defs"]["Selection"]["properties"]["block_id"]["enum"] = [b.id for b in self.blocks]
        schema["properties"]["selections"].update(minItems=len(self.blocks), maxItems=len(self.blocks))
        schema["properties"]["source_ids"]["items"] = (
            {"type": "string", "enum": sorted(self.source_ids)} if self.source_ids else {"type": "string"})
        schema["properties"]["source_ids"]["maxItems"] = len(self.source_ids)
        return schema

    def render(self, payload: dict) -> str:
        plan = SynthesisPlan.model_validate(payload)
        selected = [s.block_id for s in plan.selections]
        if len(selected) != len(set(selected)) or set(selected) != {b.id for b in self.blocks}:
            raise ValueError("Synthesis omitted or invented a capability section")
        if len(plan.source_ids) != len(set(plan.source_ids)):
            raise ValueError("Duplicate citations")
        blocks = {b.id: b for b in self.blocks}
        paragraphs = [f"{blocks[s.block_id].title}:\n{blocks[s.block_id].variants[s.variant]}"
                      for s in plan.selections]
        answer = "\n\n".join([*paragraphs, self.footer])
        # Graph-only paragraphs have explicit structural wording rather than an
        # invented textual citation. Every inline citation still uses the shared check.
        answer = validate_citations(answer, plan.source_ids, set(self.source_ids),
                                    require_every_paragraph=False, allow_empty=True)
        if re.search(r"<[/!]?[A-Za-z]|\]\(|https?://|[\x00-\x08\x0b\x0c\x0e-\x1f]", answer):
            raise ValueError("Unsafe presentation content")
        return answer


def single_tool_context(context: EvidenceContext, tool: str, data: ImpactData | None = None) -> CombinedContext:
    paths = ()
    if data is not None:
        paths = tuple(tuple(next(e.id for e in context.graph.edges
                                 if (e.source, e.type, e.target) == (p.source, p.type, p.target))
                            for p in finding.path_edges)
                      for finding in data.direct_impact + data.indirect_impact)
    title = {"decision_trace": "Decision Trace", "impact_analysis": "Impact Analysis", "find_expert": "Expert Finder", "find_stale_knowledge": "Knowledge Freshness"}[tool]
    return merge_contexts([ToolEvidence(tool, title, "trace_decision" if tool == "decision_trace"
                                       else tool, context, paths)])


def prepare_synthesis(context: CombinedContext) -> SynthesisPacket:
    if context.status == "insufficient_evidence" or not context.graph.nodes:
        raise ValueError("Insufficient validated evidence for hosted synthesis")
    nodes, edges = {n.id: n for n in context.graph.nodes}, {e.id: e for e in context.graph.edges}
    sources = {s.id: s for s in context.sources}
    blocks = []
    for tool, provenance in context.per_tool.items():
        if provenance.state != "validated":
            continue
        if tool not in {"decision_trace", "impact_analysis", "find_expert", "find_stale_knowledge"}:
            raise ValueError("Capability has no grounded presentation renderer")
        if not provenance.summary:
            raise ValueError("Missing tool-local validated narrative")
        recorded, explanation = provenance.summary, provenance.summary
        if tool == "decision_trace":
            for id in provenance.node_ids:
                decision = nodes[id]
                if decision.type != "Decision" or decision.properties.get("status") != "accepted":
                    continue
                for source_id in provenance.source_ids:
                    source = sources[source_id]
                    original = f"{decision.label}: {source.snippet} [{source.id}]"
                    if original in recorded:
                        explanation = explanation.replace(original, f"The accepted decision {decision.label} "
                            f"records its rationale in this retrieved excerpt: “{source.snippet}” [{source.id}]", 1)
        if tool == "impact_analysis":
            for ids in provenance.relationship_paths:
                path = [edges[id] for id in ids]
                dependent = nodes[path[-1].source]
                title = "Direct impact" if len(path) == 1 else "Potential downstream impact"
                stored = "; ".join(f"{e.source} -[{e.type}]-> {e.target}" for e in path)
                original = f"{title}: {dependent.label} (depth {len(path)}). Stored path: {stored}."
                if original not in recorded:
                    raise ValueError("Impact path does not match validated narrative")
                relations = "; ".join(f"{nodes[e.source].label} "
                    f"{'uses' if e.type == 'USES' else 'depends on'} {nodes[e.target].label}"
                    for e in reversed(path))
                natural = (f"Structural graph evidence: {dependent.label} ({dependent.id}) could be affected "
                           f"{'directly' if len(path) == 1 else 'indirectly'} through {len(path)} "
                           f"{'hop' if len(path) == 1 else 'hops'}: {relations}.")
                explanation = explanation.replace(original, natural, 1)
                recorded = recorded.replace(original, original.replace("-[", "—").replace("]->", "→"), 1)
        allowed = set(provenance.source_ids)
        # Validate each variant locally; source excerpts cannot smuggle new citation IDs.
        for text in (recorded, explanation):
            cited = list(dict.fromkeys(re.findall(r"\[([^\]]+)\]", text)))
            validate_citations(text, cited, allowed, require_every_paragraph=False, allow_empty=True)
        blocks.append(SynthesisBlock(f"b{len(blocks)}", {"decision_trace": "Historical decision evidence",
                                     "impact_analysis": "Current relationships and potential impact",
                                     "find_expert": "Evidence-backed expert rankings",
                                     "find_stale_knowledge": "Documents recommended for review"}[tool], {
                                         "recorded": recorded, "explanation": explanation}))
    if not blocks or len(blocks) > 4:
        raise ValueError("No bounded synthesis sections")
    footer = f"Evidence status: {context.status.replace('_', ' ')}."
    if context.status == "partially_supported":
        footer += " Some requested evidence is incomplete; this explanation cannot resolve those gaps."
    if "impact_analysis" in context.per_tool:
        footer += " Potential downstream impact is not guaranteed failure; historical sources do not prove failure propagation."
    missing = [p for p in context.summary.split("\n\n") if p.startswith("Missing evidence:")]
    footer = "\n\n".join([footer, *missing])
    evidence = {
        "entities": [{"id": n.id, "type": n.type, "label": n.label,
                      **({"status": n.properties.get("status")} if n.type == "Decision" else {})}
                     for n in context.graph.nodes],
        "paths": [{"source": e.source, "type": e.type, "target": e.target} for e in context.graph.edges],
        "sources": [s.model_dump(exclude={"metadata"}) for s in context.sources],
        "support_status": context.status,
        "tool_completeness": {tool: {"status": p.status, "state": p.state,
                                     "source_ids": list(p.source_ids)} for tool, p in context.per_tool.items()},
    }
    return SynthesisPacket(evidence, blocks, footer, frozenset(sources))
