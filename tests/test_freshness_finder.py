from pathlib import Path
from types import SimpleNamespace

import pytest

from app.graph.freshness import find_stale_knowledge
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
    """Read-only GraphClient double over the real ingested NovaPay schema."""

    def __init__(self, adapter):
        self.nodes = adapter.all_nodes()
        self.relationships = list(adapter.all_relationships().values())

    def _node(self, entity_id):
        return Node(self.nodes[entity_id])

    def _relationships(self, rel_type, target_id):
        return [
            rel
            for rel in self.relationships
            if rel["rel_type"] == rel_type and rel["target_id"] == target_id
        ]

    def execute(self, query, params=None):
        params = params or {}
        if "RETURN entity" in query:
            expected, normalized = (
                params["entity"].casefold(),
                params["normalized_entity"],
            )
            rows = [
                (self._node(entity_id),)
                for entity_id, record in self.nodes.items()
                if entity_id.casefold() == expected
                or str(record.get("name", "")).casefold() == normalized
                or str(record.get("title", "")).casefold() == normalized
            ]
        elif "RETURN document, relationship, service" in query:
            rows = [
                (
                    self._node(rel["source_id"]),
                    Relationship(rel),
                    self._node(rel["target_id"]),
                )
                for rel in self._relationships("DESCRIBES", params["service_id"])
            ]
        elif "RETURN decision, documented, document, affects, service" in query:
            rows = []
            for documented in self.relationships:
                if documented["rel_type"] != "DOCUMENTED_IN":
                    continue
                for affects in self._relationships("AFFECTS", params["service_id"]):
                    if affects["source_id"] == documented["source_id"]:
                        rows.append(
                            (
                                self._node(documented["source_id"]),
                                Relationship(documented),
                                self._node(documented["target_id"]),
                                Relationship(affects),
                                self._node(affects["target_id"]),
                            )
                        )
        elif "RETURN decision, relationship, service" in query:
            rows = [
                (
                    self._node(rel["source_id"]),
                    Relationship(rel),
                    self._node(rel["target_id"]),
                )
                for rel in self._relationships("AFFECTS", params["service_id"])
                if self.nodes[rel["source_id"]]["entity_type"] == "Decision"
                and self.nodes[rel["source_id"]].get("status") == "accepted"
            ]
        elif "RETURN commit, relationship, service" in query:
            rows = [
                (
                    self._node(rel["source_id"]),
                    Relationship(rel),
                    self._node(rel["target_id"]),
                )
                for rel in self._relationships("CHANGES", params["service_id"])
                if self.nodes[rel["source_id"]].get("architecture_change")
            ]
        elif "RETURN incident, relationship, service" in query:
            rows = [
                (
                    self._node(rel["source_id"]),
                    Relationship(rel),
                    self._node(rel["target_id"]),
                )
                for rel in self._relationships("AFFECTS", params["service_id"])
                if self.nodes[rel["source_id"]]["entity_type"] == "Incident"
            ]
        elif "RETURN chunk, relationship, source" in query:
            source_ids = set(params["source_ids"])
            rows = [
                (
                    self._node(rel["source_id"]),
                    Relationship(rel),
                    self._node(rel["target_id"]),
                )
                for rel in self.relationships
                if rel["rel_type"].startswith("FROM_")
                and rel["target_id"] in source_ids
            ]
        else:
            raise AssertionError(f"Unexpected query: {query}")
        return SimpleNamespace(result_set=rows)


class CappedDocumentClient(AdapterClient):
    def execute(self, query, params=None):
        result = super().execute(query, params)
        if "RETURN document, relationship, service" in query and result.result_set:
            return SimpleNamespace(result_set=(result.result_set * 50)[:50])
        return result


@pytest.fixture
def adapter():
    graph = InMemoryGraphAdapter()
    result = run_ingestion(DATA_DIR, adapter=graph)
    assert result.status == "success", result.errors
    return graph


def test_architecture_overview_is_a_review_candidate_with_real_paths(adapter):
    result = find_stale_knowledge(AdapterClient(adapter), "Payment Service")
    assert set(result) == {"data", "sources", "nodes", "edges", "warnings"}
    architecture = next(
        item
        for item in result["data"]["review_candidates"]
        if item["document_id"] == "doc:architecture-overview"
    )
    assert {trigger["id"] for trigger in architecture["triggers"]} == {
        "decision:D-007",
        "commit:8fae2",
        "incident:INC-17",
    }
    assert architecture["document_path"] == [
        {
            "source": "doc:architecture-overview",
            "type": "DESCRIBES",
            "target": "service:payment-service",
        }
    ]
    signatures = {
        (edge["source"], edge["type"], edge["target"]) for edge in result["edges"]
    }
    assert ("commit:8fae2", "CHANGES", "service:payment-service") in signatures
    assert ("chunk:commit:8fae2:0", "FROM_COMMIT", "commit:8fae2") in signatures
    assert {source["id"] for source in result["sources"]} >= {
        "doc:architecture-overview",
        "commit:8fae2",
    }


def test_documents_updated_after_events_are_not_flagged(adapter):
    result = find_stale_knowledge(AdapterClient(adapter), "service:payment-service")
    candidate_ids = {
        item["document_id"] for item in result["data"]["review_candidates"]
    }
    assert "doc:ADR-7" not in candidate_ids
    assert "doc:runbook-payment-latency" not in candidate_ids


def test_unrelated_or_missing_relationships_do_not_create_candidates(adapter):
    result = find_stale_knowledge(AdapterClient(adapter), "service:checkout-service")
    assert result["data"]["review_candidates"] == []
    assert result["warnings"] == [
        "No documents were found describing or documenting this service."
    ]
    adapter._relationships.pop(
        "doc:architecture-overview|DESCRIBES|service:payment-service"
    )
    missing_doc_link = find_stale_knowledge(AdapterClient(adapter), "Payment Service")
    assert all(
        item["document_id"] != "doc:architecture-overview"
        for item in missing_doc_link["data"]["review_candidates"]
    )


def test_missing_event_to_service_relationship_is_not_reported(adapter):
    adapter._relationships.pop("commit:8fae2|CHANGES|service:payment-service")
    result = find_stale_knowledge(AdapterClient(adapter), "Payment Service")
    architecture = next(
        item
        for item in result["data"]["review_candidates"]
        if item["document_id"] == "doc:architecture-overview"
    )
    assert {trigger["id"] for trigger in architecture["triggers"]} == {
        "decision:D-007",
        "incident:INC-17",
    }


def test_missing_timestamps_are_reported_without_guessing(adapter):
    adapter.get_node("doc:architecture-overview").pop("updated_at")
    adapter.get_node("commit:8fae2").pop("timestamp")
    result = find_stale_knowledge(AdapterClient(adapter), "Payment Service")
    assert all(
        item["document_id"] != "doc:architecture-overview"
        for item in result["data"]["review_candidates"]
    )
    assert (
        "Document doc:architecture-overview has no comparable updated_at timestamp."
        in result["warnings"]
    )
    assert (
        "Commit commit:8fae2 has no comparable timestamp timestamp."
        in result["warnings"]
    )


def test_results_are_deterministic_and_bounded_warnings_are_honest(adapter):
    first = find_stale_knowledge(AdapterClient(adapter), "Payment Service")
    second = find_stale_knowledge(AdapterClient(adapter), "Payment Service")
    assert first["data"]["review_candidates"] == second["data"]["review_candidates"]
    capped = find_stale_knowledge(CappedDocumentClient(adapter), "Payment Service")
    assert (
        "Document discovery may be incomplete because the query reached its cap of 50 rows."
        in capped["warnings"]
    )


@pytest.mark.parametrize(
    "entity, warning",
    [
        ("", "entity must be a non-empty string."),
        ("unknown-service", "No graph entity found for unknown-service."),
        ("Redis", "Knowledge freshness currently supports Service entities only."),
    ],
)
def test_invalid_unknown_and_non_service_entities_are_honest(adapter, entity, warning):
    result = find_stale_knowledge(AdapterClient(adapter), entity)
    assert result["data"]["review_candidates"] == []
    assert warning in result["warnings"]
