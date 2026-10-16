"""Replaceable graph and source boundary. No teammate-owned Cypher is duplicated."""
import asyncio
import importlib
import inspect
import json
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from .config import Settings
from .models import Source, TraceInput, TraceResult


class GraphUnavailable(Exception):
    pass


class GraphContractError(Exception):
    pass


class SourceRetriever(Protocol):
    async def find_sources(self, source_ids: list[str]) -> list[Source]: ...


class GraphGateway(SourceRetriever, Protocol):
    async def health(self) -> bool:
        """Verify the real graph tool can query the configured graph."""
        ...

    async def trace_decision(self, query: TraceInput) -> TraceResult: ...


class FixtureGateway:
    """Explicit development data, never a fallback from real mode."""
    def __init__(self):
        path = Path(__file__).parent / "fixtures" / "novapay.development.json"
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        self.trace = TraceResult.model_validate(payload["trace"])
        self.sources = [Source.model_validate(s) for s in payload["sources"]]

    async def health(self) -> bool:
        return True

    async def trace_decision(self, query: TraceInput) -> TraceResult:
        if (query.service.casefold(), query.technology.casefold()) != ("payment service", "redis"):
            return TraceResult()
        return self.trace.model_copy(deep=True)

    async def find_sources(self, source_ids: list[str]) -> list[Source]:
        return [s.model_copy(deep=True) for s in self.sources if s.id in source_ids]


class FalkorGateway:
    """Load a trusted, operator-configured module:factory once at startup.

    The factory returns the async GraphGateway protocol above. It owns entity
    resolution, bounded Cypher traversal and retrieval of authoritative sources.
    Factory imports are never controlled by requests. Failures never load fixtures.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self.delegate: GraphGateway | None = None
        if settings.graph_factory:
            try:
                module, factory = settings.graph_factory.split(":", 1)
                candidate = getattr(importlib.import_module(module), factory)(settings)
                if not all(inspect.iscoroutinefunction(getattr(candidate, m, None))
                           for m in ("health", "trace_decision", "find_sources")):
                    raise TypeError("Graph gateway must implement async protocol")
                self.delegate = candidate
            except Exception:
                # Health reports unavailable. Import errors may contain credentials.
                self.delegate = None

    async def database_health(self) -> bool:
        def probe() -> bool:
            from falkordb import FalkorDB
            db = FalkorDB(
                host=self.settings.falkordb_host, port=self.settings.falkordb_port,
                username=self.settings.falkordb_username or None,
                password=(self.settings.falkordb_password.get_secret_value()
                          if self.settings.falkordb_password else None),
                ssl=self.settings.falkordb_ssl, socket_connect_timeout=2, socket_timeout=2,
            )
            try:
                # A Redis PING alone does not prove the graph module/data is available.
                if self.settings.graph_name not in db.list_graphs():
                    return False
                db.select_graph(self.settings.graph_name).ro_query(
                    "MATCH (n) RETURN n.id LIMIT 1", timeout=1500,
                )
                return True
            finally:
                db.connection.close()
        try:
            return await asyncio.wait_for(asyncio.to_thread(probe), timeout=4)
        except Exception:
            return False

    async def health(self) -> bool:
        if not self.delegate:
            return False
        try:
            return bool(await asyncio.wait_for(self.delegate.health(), timeout=4))
        except Exception:
            return False

    async def trace_decision(self, query: TraceInput) -> TraceResult:
        if not self.delegate:
            raise GraphUnavailable()
        try:
            result = await asyncio.wait_for(self.delegate.trace_decision(query), timeout=15)
        except GraphContractError:
            raise
        except Exception as exc:
            raise GraphUnavailable() from exc
        try:
            return TraceResult.model_validate(result)
        except ValidationError as exc:
            raise GraphContractError("Invalid trace result") from exc

    async def find_sources(self, source_ids: list[str]) -> list[Source]:
        if not self.delegate:
            raise GraphUnavailable()
        try:
            records = await asyncio.wait_for(self.delegate.find_sources(source_ids), timeout=10)
        except GraphContractError:
            raise
        except Exception as exc:
            raise GraphUnavailable() from exc
        try:
            return TypeAdapter(list[Source]).validate_python(records)
        except ValidationError as exc:
            raise GraphContractError("Invalid source records") from exc


def create_gateway(settings: Settings) -> GraphGateway:
    return FixtureGateway() if settings.graph_mode == "fixture" else FalkorGateway(settings)
