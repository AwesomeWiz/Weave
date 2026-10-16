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

    if decision is None:
        raise AssertionError("Expected to find a decision")

    assert decision["id"] == "decision:D-007"
    assert result["data"]["decision_status"] == "accepted"
    assert result["data"]["service"]["id"] == "service:payment-service"
    assert result["data"]["technology"]["id"] == "tech:redis"

    print("\nDecision trace smoke test: PASS")


if __name__ == "__main__":
    main()