"""Grounding through retrieved Decision -> Source <- Chunk paths."""
import copy

import pytest

from app.context import build_context
from app.models import Source, TraceInput, TraceResult


TARGET = TraceInput(service="Payment Service", technology="Redis")


@pytest.fixture
def chain():
    source_id, chunk_id = "issue:PAY-42", "chunk:issue:PAY-42:0"
    text = "Use Redis to reduce repeated payment read latency during bursts."
    def node(id, kind, label, properties=None):
        return {"id": id, "type": kind, "label": label, "properties": properties or {}}
    paths = [("decision:D-007", "AFFECTS", "service:payment-service"),
             ("decision:D-007", "INTRODUCES", "tech:redis"),
             ("service:payment-service", "USES", "tech:redis"),
             ("decision:D-007", "SUPPORTED_BY", source_id),
             (chunk_id, "FROM_ISSUE", source_id)]
    trace = TraceResult.model_validate({
        "graph": {"nodes": [
            node("decision:D-007", "Decision", "Cache payment reads", {"status": "accepted"}),
            node("service:payment-service", "Service", "Payment Service"),
            node("tech:redis", "Technology", "Redis"),
            node(source_id, "Issue", "Reduce read latency"),
            node(chunk_id, "Chunk", "Issue excerpt", {"source_id": source_id,
                 "source_type": "Issue", "chunk_index": 0, "text": text}),
        ], "edges": [{"id": f"{s}|{kind}|{t}", "source": s, "type": kind, "target": t}
                     for s, kind, t in paths]},
        "source_ids": [source_id], "decision_ids": ["decision:D-007"],
    })
    source = Source(id=source_id, type="Issue", title="Reduce read latency", snippet=text,
                    entity_ids=[source_id], metadata={"source_id": source_id,
                    "source_type": "Issue", "chunk_ids": [chunk_id]})
    return trace, source


def test_complete_retrieved_path_supports_rationale_without_inventing_edges_or_citations(chain):
    trace, source = chain
    before = trace.model_dump()
    original = source.model_dump()
    context = build_context(trace, [source], TARGET)
    assert context.status == "supported" and context.can_explain
    assert "[issue:PAY-42]" in context.summary
    assert "[decision:D-007]" not in context.summary
    assert trace.model_dump() == before
    assert source.model_dump() == original
    assert context.graph.model_dump() == trace.graph.model_dump()


@pytest.mark.parametrize("damage", ["supported_by", "from", "reverse_from", "reverse_support",
                                    "wrong_from_type", "chunk_id", "parent", "chunk_text",
                                    "snippet", "unaccepted", "uses", "affects", "introduces"])
def test_missing_or_inconsistent_provenance_cannot_establish_rationale(chain, damage):
    trace, source = chain
    if damage in {"supported_by", "from", "uses", "affects", "introduces"}:
        kind = {"supported_by": "SUPPORTED_BY", "from": "FROM_ISSUE"}.get(damage, damage.upper())
        trace.graph.edges = [e for e in trace.graph.edges if e.type != kind]
    elif damage in {"reverse_from", "reverse_support"}:
        kind = "FROM_ISSUE" if damage == "reverse_from" else "SUPPORTED_BY"
        edge = next(e for e in trace.graph.edges if e.type == kind)
        edge.source, edge.target = edge.target, edge.source
    elif damage == "wrong_from_type":
        next(e for e in trace.graph.edges if e.type == "FROM_ISSUE").type = "FROM_DOCUMENT"
    elif damage == "chunk_id":
        source.metadata["chunk_ids"] = ["chunk:unrelated:0"]
    elif damage == "parent":
        trace.graph.nodes[-1].properties["source_id"] = "issue:unrelated"
    elif damage == "chunk_text":
        trace.graph.nodes[-1].properties["text"] = "Unrelated stored text."
    elif damage == "snippet":
        source.snippet = "An unsupported replacement rationale."
    else:
        trace.graph.nodes[0].properties["status"] = "proposed"
    context = build_context(trace, [source], TARGET)
    assert context.status == "partially_supported" and not context.can_explain
    assert "rationale is incomplete" in context.summary


def test_multichunk_order_and_context_truncation_are_preserved(chain):
    trace, source = chain
    second = trace.graph.nodes[-1].model_copy(deep=True)
    second.id = "chunk:issue:PAY-42:1"
    second.properties.update(chunk_index=1, text="Stored consequence. " * 150)
    trace.graph.nodes.append(second)
    edge = copy.deepcopy(trace.graph.edges[-1])
    edge.id, edge.source = "second-provenance", second.id
    trace.graph.edges.append(edge)
    source.metadata["chunk_ids"] = [second.id, "chunk:issue:PAY-42:0"]
    source.snippet += "\n\n" + second.properties["text"].strip()
    context = build_context(trace, [source], TARGET)
    assert context.status == "supported"
    assert len(context.sources[0].snippet) == 1600


def test_missing_one_contributing_chunk_cannot_ground_aggregate_text(chain):
    trace, source = chain
    source.metadata["chunk_ids"].append("chunk:issue:PAY-42:1")
    assert build_context(trace, [source], TARGET).status == "partially_supported"
