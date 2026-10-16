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
        *,
        username: str | None = None,
        password: str | None = None,
        ssl: bool = False,
        socket_connect_timeout: float = 2,
        socket_timeout: float = 5,
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
            else os.getenv("FALKORDB_GRAPH_NAME", os.getenv("FALKORDB_GRAPH", "novapay"))
        )

        self.db = FalkorDB(
            host=self.host,
            port=self.port,
            username=username, password=password, ssl=ssl,
            socket_connect_timeout=socket_connect_timeout, socket_timeout=socket_timeout,
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
                return self.graph.query(query, timeout=5000)
            return self.graph.query(query, params, timeout=5000)
        except Exception as exc:
            raise RuntimeError(
                f"FalkorDB query failed on graph "
                f"'{self.graph_name}': {exc}"
            ) from exc

    def health_check(self) -> bool:
        """Return True if a simple graph query succeeds."""
        try:
            if self.graph_name not in self.db.list_graphs():
                return False
            result = self.execute("RETURN 1 AS ok")
            return bool(
                result.result_set
                and result.result_set[0][0] == 1
            )
        except Exception:
            return False

    def close(self) -> None:
        self.db.connection.close()

    def reset_graph(self) -> None:
        """Delete all nodes and relationships in this graph.

        Use only for deliberate resets or isolated test graphs.
        """
        self.execute("MATCH (n) DETACH DELETE n")
