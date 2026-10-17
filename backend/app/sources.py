"""Map Alen's graph-backed source records onto the existing public Source type."""
import asyncio

from pydantic import ValidationError

from .config import Settings
from .graph import GraphContractError, GraphUnavailable
from .models import Source


class WeaveDataSourceRetriever:
    def __init__(self, settings: Settings):
        if settings.graph_mode != "falkordb":
            raise ValueError("weave_data retrieval requires explicit real graph mode")
        self.settings = settings

    def _retrieve(self, source_ids: list[str]) -> list[Source]:
        from weave_data.graph_adapter import FalkorDBGraphAdapter
        from weave_data.retrieval import find_sources

        config = self.settings
        # Always construct the real adapter. No local files, loader or memory adapter.
        adapter = FalkorDBGraphAdapter(
            host=config.falkordb_host, port=config.falkordb_port, graph_name=config.graph_name,
            username=config.falkordb_username or None,
            password=config.falkordb_password.get_secret_value() if config.falkordb_password else None,
            ssl=config.falkordb_ssl, socket_connect_timeout=2, socket_timeout=5,
        )
        try:
            records = find_sources(source_ids, adapter=adapter)
            return [Source(
                id=record.id, type=record.type, title=record.title, snippet=record.snippet,
                url=record.url, timestamp=record.model_dump(mode="json")["timestamp"],
                entity_ids=[record.id],
                metadata={
                    "source_id": record.id, "source_type": record.type,
                    "chunk_ids": record.chunk_ids,
                    "chunks": [chunk.model_dump(mode="json", exclude={"text"}) for chunk in record.chunks],
                },
            ) for record in records]
        finally:
            adapter.close()

    async def find_sources(self, source_ids: list[str]) -> list[Source]:
        if not source_ids:
            return []
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._retrieve, source_ids), timeout=10)
        except ValidationError as exc:
            raise GraphContractError("Invalid weave_data source payload") from exc
        except Exception as exc:
            raise GraphUnavailable() from exc
