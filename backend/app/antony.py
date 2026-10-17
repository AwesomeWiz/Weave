"""Thin async/normalization boundary around the merged teammate trace tool."""
import asyncio

from pydantic import ValidationError

from .config import Settings
from .graph import GraphContractError
from .models import ImpactInput, ImpactResult, TraceInput, TraceResult


def normalize_impact(payload: dict) -> ImpactResult:
    try:
        return ImpactResult.model_validate(payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise GraphContractError("Invalid teammate impact analysis") from exc


def normalize_trace(payload: dict) -> TraceResult:
    """Preserve returned nodes/edges; never fill in unqueried relationships."""
    try:
        data = payload["data"]
        decision = data["decision"]
        nodes, edges, sources = payload["nodes"], payload["edges"], payload["sources"]
        if not isinstance(data, dict) or not isinstance(sources, list):
            raise ValueError("Invalid trace envelope")
        if decision is None:
            if nodes or edges or sources:
                raise ValueError("Evidence without a selected decision")
            return TraceResult(warnings=payload.get("warnings") or [
                "No decision found for the requested service and technology."])
        decision_id = decision["id"]
        if not isinstance(decision_id, str) or not decision_id:
            raise ValueError("Missing decision ID")
        source_ids = []
        for source in sources:
            source_id = source["id"]
            if not isinstance(source_id, str) or not source_id:
                raise ValueError("Invalid canonical source ID")
            if source_id not in source_ids:
                source_ids.append(source_id)
        trace = TraceResult.model_validate({
            "graph": {"nodes": nodes, "edges": edges},
            "source_ids": source_ids, "decision_ids": [decision_id],
            "warnings": payload.get("warnings", []),
        })
        selected = next((n for n in trace.graph.nodes if n.id == decision_id and n.type == "Decision"), None)
        if selected is None or selected.properties != decision:
            raise ValueError("Decision payload conflicts with evidence node")
        if data.get("decision_status") != selected.properties.get("status"):
            raise ValueError("Conflicting decision status")
        if (not any(e.type == "USES" for e in trace.graph.edges)
                and not any("USES" in warning for warning in trace.warnings)):
            trace.warnings.append("The trace tool did not return a Service USES Technology relationship.")
        return trace
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise GraphContractError("Invalid teammate decision trace") from exc


class AntonyGateway:
    def __init__(self, settings: Settings):
        if settings.graph_mode != "falkordb":
            raise ValueError("Antony's graph tool requires real graph mode")
        self.settings = settings

    def _client(self):
        from weave_graph.client import GraphClient

        config = self.settings
        return GraphClient(
            host=config.falkordb_host, port=config.falkordb_port, graph_name=config.graph_name,
            username=config.falkordb_username or None,
            password=config.falkordb_password.get_secret_value() if config.falkordb_password else None,
            ssl=config.falkordb_ssl, socket_connect_timeout=2, socket_timeout=5,
        )

    async def health(self) -> bool:
        def probe():
            client = self._client()
            try:
                return client.health_check()
            finally:
                client.close()
        return await asyncio.to_thread(probe)

    async def trace_decision(self, query: TraceInput) -> TraceResult:
        from weave_graph.trace import trace_decision

        # The Phase 1 router resolves only these two documented display aliases.
        # Canonical IDs pass through unchanged; no evidence/source IDs are canned.
        service_id = {"payment service": "service:payment-service"}.get(query.service.casefold(), query.service)
        technology_id = {"redis": "tech:redis"}.get(query.technology.casefold(), query.technology)
        if not service_id.startswith("service:") or not technology_id.startswith("tech:"):
            return TraceResult(warnings=["The requested entity aliases could not be resolved."])

        def retrieve():
            client = self._client()
            try:
                return trace_decision(client, service_id=service_id, technology_id=technology_id)
            finally:
                client.close()
        return normalize_trace(await asyncio.to_thread(retrieve))

    async def find_sources(self, source_ids: list[str]):
        from .sources import WeaveDataSourceRetriever
        return await WeaveDataSourceRetriever(self.settings).find_sources(source_ids)

    async def impact_analysis(self, query: ImpactInput) -> ImpactResult:
        from weave_graph.impact import impact_analysis

        def retrieve():
            client = self._client()
            try:
                return impact_analysis(client, query.entity_id, max_depth=query.max_depth)
            finally:
                client.close()
        return normalize_impact(await asyncio.to_thread(retrieve))


def create_gateway(settings: Settings) -> AntonyGateway:
    return AntonyGateway(settings)
