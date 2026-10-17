from pathlib import Path
from types import SimpleNamespace

import pytest
from weave_graph.experts import find_expert

from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import run_ingestion

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "novapay"


class Node:
    def __init__(self, record):
        self.properties = {
            key: value for key, value in record.items() if key != "entity_type"
        }
        self.labels = [record["entity_type"]]


class Relationship:
    def __init__(self, record):
        self.relation = record["rel_type"]
        self.properties = record["properties"]


class AdapterClient:
    """Small read-only GraphClient double backed by the real ingested schema."""

    def __init__(self, adapter):
        self.nodes = adapter.all_nodes()
        self.relationships = list(adapter.all_relationships().values())

    def execute(self, query, params=None):
        params = params or {}
        if "RETURN topic" in query:
            allowed = {
                "Service",
                "Technology",
                "Decision",
                "Issue",
                "Document",
                "Message",
            }
            rows = [
                (Node(record),)
                for record in self.nodes.values()
                if record["entity_type"] in allowed
            ]
        elif "RETURN source, relationship, target" in query:
            ids = set(params["entity_ids"])
            types = set(params["relationship_types"])
            rows = [
                (
                    Node(self.nodes[rel["source_id"]]),
                    Relationship(rel),
                    Node(self.nodes[rel["target_id"]]),
                )
                for rel in self.relationships
                if rel["rel_type"] in types
                and (rel["source_id"] in ids or rel["target_id"] in ids)
            ]
        elif "RETURN person, relationship, entity" in query:
            ids = set(params["entity_ids"])
            types = set(params["relationship_types"])
            rows = [
                (
                    Node(self.nodes[rel["source_id"]]),
                    Relationship(rel),
                    Node(self.nodes[rel["target_id"]]),
                )
                for rel in self.relationships
                if rel["rel_type"] in types
                and rel["source_id"].startswith("person:")
                and rel["target_id"] in ids
            ]
        elif "RETURN issue, relationship, person" in query:
            ids = set(params["entity_ids"])
            rows = [
                (
                    Node(self.nodes[rel["source_id"]]),
                    Relationship(rel),
                    Node(self.nodes[rel["target_id"]]),
                )
                for rel in self.relationships
                if rel["rel_type"] == "ASSIGNED_TO" and rel["source_id"] in ids
            ]
        elif "RETURN person, membership, team, owns, service" in query:
            ids = set(params["entity_ids"])
            rows = []
            for member in self.relationships:
                if member["rel_type"] != "MEMBER_OF":
                    continue
                for owns in self.relationships:
                    if (
                        owns["rel_type"] == "OWNS"
                        and owns["source_id"] == member["target_id"]
                        and owns["target_id"] in ids
                    ):
                        rows.append(
                            (
                                Node(self.nodes[member["source_id"]]),
                                Relationship(member),
                                Node(self.nodes[member["target_id"]]),
                                Relationship(owns),
                                Node(self.nodes[owns["target_id"]]),
                            )
                        )
        elif "RETURN chunk, relationship, source" in query:
            ids = set(params["source_ids"])
            rows = [
                (
                    Node(self.nodes[rel["source_id"]]),
                    Relationship(rel),
                    Node(self.nodes[rel["target_id"]]),
                )
                for rel in self.relationships
                if rel["rel_type"].startswith("FROM_") and rel["target_id"] in ids
            ]
        else:
            raise AssertionError(f"Unexpected query: {query}")
        return SimpleNamespace(result_set=rows)


class NoChunkAdapterClient(AdapterClient):
    """Graph double for testing evidence graphs with unavailable chunks."""

    def execute(self, query, params=None):
        if "RETURN chunk, relationship, source" in query:
            return SimpleNamespace(result_set=[])
        return super().execute(query, params)


class AmbiguousTopicAdapterClient(AdapterClient):
    """Graph double with two equally exact service names."""

    def __init__(self, adapter):
        super().__init__(adapter)
        duplicate = dict(self.nodes["service:payment-service"])
        duplicate["id"] = "service:payment-service-copy"
        self.nodes[duplicate["id"]] = duplicate


class CappedTraversalAdapterClient(AdapterClient):
    """Graph double that makes the bounded neighborhood query hit its cap."""

    def execute(self, query, params=None):
        result = super().execute(query, params)
        if "RETURN source, relationship, target" in query and result.result_set:
            return SimpleNamespace(result_set=(result.result_set * 100)[:100])
        return result


@pytest.fixture(scope="module")
def client():
    adapter = InMemoryGraphAdapter()
    result = run_ingestion(DATA_DIR, adapter=adapter)
    assert result.status == "success", result.errors
    return AdapterClient(adapter)


def test_payment_experts_are_ranked_from_real_graph_evidence(client):
    result = find_expert(client, "Who knows the most about Payment Service?", limit=5)

    assert set(result) == {"data", "sources", "nodes", "edges", "warnings"}
    assert [expert["person"]["id"] for expert in result["data"]["experts"]] == [
        "person:ravi",
        "person:alice",
        "person:maya",
    ]
    assert result["data"]["topics"][0]["id"] == "service:payment-service"
    assert result["warnings"] == []


def test_expert_evidence_is_directed_and_ownership_is_not_personal_ownership(client):
    result = find_expert(client, "Payment Service")
    alice = next(
        item
        for item in result["data"]["experts"]
        if item["person"]["id"] == "person:alice"
    )
    assert (
        alice["ownership_classification"] == "team_membership_with_team_owned_service"
    )
    ownership = alice["ownership"][0]
    assert ownership["path"] == [
        {"source": "person:alice", "type": "MEMBER_OF", "target": "team:payments"},
        {
            "source": "team:payments",
            "type": "OWNS",
            "target": "service:payment-service",
        },
    ]
    assert all(
        item["category"] != "team_ownership"
        for item in alice["historical_contributions"]
    )
    signatures = {
        (edge["source"], edge["type"], edge["target"]) for edge in result["edges"]
    }
    assert ("person:ravi", "AUTHORED", "commit:8fae2") in signatures
    assert ("chunk:commit:8fae2:0", "FROM_COMMIT", "commit:8fae2") in signatures


def test_sources_are_provenance_linked_to_ranked_evidence(client):
    result = find_expert(client, "Payment Service")
    evidence_ids = {
        evidence["entity_id"]
        for expert in result["data"]["experts"]
        for evidence in expert["evidence"]
    }
    provenance = {
        (edge["source"], edge["type"], edge["target"])
        for edge in result["edges"]
        if edge["type"].startswith("FROM_")
    }
    expected_types = {
        "issue:PAY-42": "FROM_ISSUE",
        "message:payment-perf-7": "FROM_MESSAGE",
        "commit:8fae2": "FROM_COMMIT",
    }
    assert {source["id"] for source in result["sources"]} == set(expected_types)
    for source in result["sources"]:
        assert source["id"] in evidence_ids
        assert (
            source["chunk_id"],
            expected_types[source["id"]],
            source["id"],
        ) in provenance


def test_result_is_deterministic_limited_and_has_real_sources(client):
    first = find_expert(client, "Payment Service", limit=2)
    second = find_expert(client, "Payment Service", limit=2)
    assert first["data"]["experts"] == second["data"]["experts"]
    assert len(first["data"]["experts"]) == 2
    assert {source["id"] for source in first["sources"]} <= {
        "issue:PAY-42",
        "message:payment-perf-7",
        "commit:8fae2",
    }


def test_missing_source_chunks_do_not_remove_graph_evidence(client):
    result = find_expert(
        NoChunkAdapterClient(
            SimpleNamespace(
                all_nodes=lambda: client.nodes,
                all_relationships=lambda: {
                    f"{rel['source_id']}|{rel['rel_type']}|{rel['target_id']}": rel
                    for rel in client.relationships
                },
            )
        ),
        "Payment Service",
    )
    assert result["sources"] == []
    assert result["data"]["experts"]
    assert result["warnings"] == [
        (
            "Missing provenance chunks for expert evidence: "
            "commit:8fae2, issue:PAY-42, message:payment-perf-7"
        )
    ]


def test_generic_and_ambiguous_topics_are_not_ranked(client):
    generic = find_expert(client, "Who is the best service expert?")
    assert generic["data"]["topics"] == []
    assert generic["data"]["experts"] == []
    assert generic["warnings"] == ["No graph topic matched the query."]

    adapter = InMemoryGraphAdapter()
    assert run_ingestion(DATA_DIR, adapter=adapter).status == "success"
    ambiguous = find_expert(AmbiguousTopicAdapterClient(adapter), "Payment Service")
    assert ambiguous["data"]["experts"] == []
    assert {topic["id"] for topic in ambiguous["data"]["topics"]} == {
        "service:payment-service",
        "service:payment-service-copy",
    }
    assert ambiguous["warnings"] == [
        (
            "Topic resolution is ambiguous: "
            "service:payment-service, service:payment-service-copy"
        )
    ]


def test_reaching_a_traversal_cap_warns_that_ranking_may_be_incomplete(client):
    capped = find_expert(
        CappedTraversalAdapterClient(
            SimpleNamespace(
                all_nodes=lambda: client.nodes,
                all_relationships=lambda: {
                    f"{rel['source_id']}|{rel['rel_type']}|{rel['target_id']}": rel
                    for rel in client.relationships
                },
            )
        ),
        "Payment Service",
    )
    assert capped["data"]["experts"]
    assert any(
        warning == "Topic evidence traversal may be incomplete because the query "
        "reached its cap of 100 rows."
        for warning in capped["warnings"]
    )


@pytest.mark.parametrize(
    "query, limit, warning",
    [
        ("", 5, "query must be a non-empty string."),
        ("Payment Service", 0, "limit must be an integer between 1 and 10."),
        ("Unknown system", 5, "No graph topic matched the query."),
    ],
)
def test_invalid_or_unmatched_queries_are_honest(client, query, limit, warning):
    result = find_expert(client, query, limit)
    assert result["data"]["experts"] == []
    assert result["sources"] == []
    assert result["nodes"] == []
    assert result["warnings"] == [warning]
