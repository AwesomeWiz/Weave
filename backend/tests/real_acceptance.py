"""Read-only acceptance assertions; no retrieval, ingestion, or seed implementation."""
from app.context import safe_url
from app.models import QueryResponse, Source


def assert_primary_evidence(data: dict, authoritative: list[Source]) -> None:
    result = QueryResponse.model_validate(data)
    assert result.metadata.graph_mode == "falkordb"
    assert result.tools_used == ["trace_decision"]
    assert result.support_status == "supported"
    assert result.answer.strip()
    nodes = {node.id: node for node in result.graph.nodes}
    decision, service, technology = "decision:D-007", "service:payment-service", "tech:redis"
    issue, message, document = "issue:PAY-42", "message:payment-perf-7", "doc:ADR-7"
    assert nodes[decision].type == "Decision"
    assert nodes[decision].properties.get("status") == "accepted"
    assert nodes[service].type == "Service"
    assert nodes[technology].type == "Technology"
    commits = [n.id for n in nodes.values()
               if n.type == "Commit" and n.id.startswith("commit:8fae2")]
    assert len(commits) == 1, "Expected one canonical implementation commit (short or full SHA)"
    commit = commits[0]
    for entity, kind in [(issue, "Issue"), (message, "Message"), (document, "Document")]:
        assert nodes[entity].type == kind
    edges = {(e.source, e.type, e.target) for e in result.graph.edges}
    assert {(service, "USES", technology), (decision, "AFFECTS", service),
            (decision, "INTRODUCES", technology), (decision, "DOCUMENTED_IN", document),
            ("incident:INC-17", "LED_TO", issue)} <= edges
    assert {(decision, "SUPPORTED_BY", issue), (issue, "LED_TO", decision)} & edges
    assert {(decision, "DISCUSSED_IN", message), (decision, "SUPPORTED_BY", message)} & edges
    assert {(decision, "IMPLEMENTED_BY", commit), (commit, "IMPLEMENTS_DECISION", decision)} & edges

    originals = {source.id: source for source in authoritative}
    assert len(originals) == len(authoritative), "Duplicate IDs in independent evidence export"
    retrieved = {source.id: source for source in result.sources}
    assert len(retrieved) == len(result.sources)
    for source in result.sources:
        assert source.metadata.get("dataset") != "development_fixture"
        assert source.id in originals, "Evidence absent from independent seeded-corpus export"
        original = originals[source.id]
        assert source.snippet and source.snippet == original.snippet.strip()[:1600]
        assert source.type == original.type and source.title == original.title
        assert source.timestamp == original.timestamp
        assert source.url == safe_url(original.url)
        assert source.metadata == original.metadata, "Source/chunk provenance changed"
        assert set(source.entity_ids) == set(original.entity_ids)
    for entity in (issue, message, document, commit):
        evidence = [s for s in result.sources if s.id == entity or (
            entity in s.entity_ids and s.metadata.get("source_id") == entity
        )]
        assert evidence, f"Missing authoritative supporting evidence for {entity}"
        for source in evidence:
            if source.id != entity:
                assert source.metadata.get("chunk_id") == source.id
                index = source.metadata.get("chunk_index")
                assert type(index) is int and index >= 0
                source_type = source.metadata.get("source_type")
                assert isinstance(source_type, str) and source_type.strip()
