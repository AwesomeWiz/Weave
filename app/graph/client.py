import os
from typing import Any

from falkordb import FalkorDB


class GraphClient:
    """Client for interacting with FalkorDB."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        graph_name: str | None = None,
    ) -> None:
        self.host = (
            host if host is not None
            else os.getenv("FALKORDB_HOST", "localhost")
        )
        self.port = (
            port if port is not None
            else int(os.getenv("FALKORDB_PORT", "6379"))
        )
        self.graph_name = (
            graph_name
            if graph_name is not None
            else os.getenv("FALKORDB_GRAPH_NAME", "weave")
        )

        self.db = FalkorDB(
            host=self.host,
            port=self.port,
        )
        self.graph = self.db.select_graph(self.graph_name)

    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ):
        """Execute a Cypher query against the configured graph."""
        try:
            if params is None:
                return self.graph.query(query)
            return self.graph.query(query, params)
        except Exception as exc:
            raise RuntimeError(
                f"FalkorDB query failed on graph "
                f"'{self.graph_name}': {exc}"
            ) from exc

    def health_check(self) -> bool:
        """Return True if a simple graph query succeeds."""
        try:
            result = self.execute("RETURN 1 AS ok")
            return bool(
                result.result_set
                and result.result_set[0][0] == 1
            )
        except Exception:
            return False

    def reset_graph(self) -> None:
        """Delete all nodes and relationships in this graph.

        Use only for deliberate resets or isolated test graphs.
        """
        self.execute("MATCH (n) DETACH DELETE n")