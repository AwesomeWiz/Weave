import json

from app.graph.client import GraphClient
from app.graph.trace import trace_decision


def main() -> None:
    client = GraphClient(graph_name="novapay")

    if not client.health_check():
        raise RuntimeError("FalkorDB health check failed")

    result = trace_decision(client)
    print(json.dumps(result, indent=2, default=str))

    decision = result["data"]["decision"]

    assert decision is not None, "Expected to find a decision"
    assert decision["id"] == "decision:D-007"
    assert result["data"]["decision_status"] == "accepted"
    assert result["data"]["service"]["id"] == "service:payment-service"
    assert result["data"]["technology"]["id"] == "tech:redis"

    edge_signatures = {
        (edge["source"], edge["type"], edge["target"])
        for edge in result["edges"]
    }

    expected_edges = {
        (
            "decision:D-007",
            "AFFECTS",
            "service:payment-service",
        ),
        (
            "decision:D-007",
            "INTRODUCES",
            "tech:redis",
        ),
        (
            "service:payment-service",
            "USES",
            "tech:redis",
        ),
        (
            "incident:INC-17",
            "LED_TO",
            "issue:PAY-42",
        ),
        (
            "decision:D-007",
            "SUPPORTED_BY",
            "issue:PAY-42",
        ),
        (
            "decision:D-007",
            "SUPPORTED_BY",
            "message:payment-perf-7",
        ),
        (
            "decision:D-007",
            "DOCUMENTED_IN",
            "doc:ADR-7",
        ),
        (
            "decision:D-007",
            "IMPLEMENTED_BY",
            "commit:8fae2",
        ),
    }

    missing_edges = expected_edges - edge_signatures
    assert not missing_edges, f"Missing graph edges: {missing_edges}"

    # Verify that chunks retain canonical source provenance.
    source_chunk_pairs = {
        (source["id"], source["chunk_id"])
        for source in result["sources"]
    }

    expected_sources = {
        ("issue:PAY-42", "chunk:issue:PAY-42:0"),
        ("message:payment-perf-7", "chunk:message:payment-perf-7:0"),
        ("commit:8fae2", "chunk:commit:8fae2:0"),
        ("doc:ADR-7", "chunk:doc:ADR-7:0"),
    }

    missing_sources = expected_sources - source_chunk_pairs
    assert not missing_sources, f"Missing source/chunk pairs: {missing_sources}"

    # Verify chunk provenance edges preserve Chunk -> Source direction.
    provenance_edges = {
        (edge["source"], edge["type"], edge["target"])
        for edge in result["edges"]
        if edge["type"].startswith("FROM_")
    }

    expected_provenance = {
        ("chunk:issue:PAY-42:0", "FROM_ISSUE", "issue:PAY-42"),
        (
            "chunk:message:payment-perf-7:0",
            "FROM_MESSAGE",
            "message:payment-perf-7",
        ),
        ("chunk:commit:8fae2:0", "FROM_COMMIT", "commit:8fae2"),
        ("chunk:doc:ADR-7:0", "FROM_DOCUMENT", "doc:ADR-7"),
    }

    missing_provenance = expected_provenance - provenance_edges
    assert not missing_provenance, (
        f"Missing or incorrectly directed provenance edges: {missing_provenance}"
    )

    assert result["warnings"] == [], (
        f"Unexpected trace warnings: {result['warnings']}"
    )

    print("\nDecision trace regression test: PASS")


if __name__ == "__main__":
    main()