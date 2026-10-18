"""Validate and seed only the Redis/FalkorDB child owned by this demo boot."""
import os
import sys
import time

from deploy.render.start import ROOT, runtime_environment


def wait_for_owned_graph(client, expected_pid, *, timeout=60):
    from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if client.ping():
                if client.info("server").get("process_id") != expected_pid:
                    raise ValueError("Refusing an unowned database process")
                # PING alone is not proof that the genuine graph module loaded.
                graphs = client.execute_command("GRAPH.LIST")
                if graphs:
                    raise ValueError("Refusing an existing graph")
                print("Render demo: owned FalkorDB GRAPH.LIST succeeded; module loaded; empty graph confirmed",
                      flush=True)
                return
        except (RedisConnectionError, RedisTimeoutError):
            pass
        time.sleep(0.5)
    raise RuntimeError("Local FalkorDB readiness deadline exceeded")


def verify_seed(adapter, records, relationships, chunks):
    from weave_data.retrieval import find_sources

    def rows(query):
        return adapter._graph.ro_query(query, timeout=5000).result_set

    expected_ids = {record.id for record in records} | {chunk.id for chunk in chunks}
    nodes = rows("MATCH (n) RETURN n.id LIMIT 27")
    if len(nodes) != 26 or {row[0] for row in nodes} != expected_ids:
        raise ValueError("Persisted entity/chunk inventory mismatch")
    if rows("MATCH (c:Chunk) RETURN count(c)") != [[6]]:
        raise ValueError("Persisted chunk count mismatch")
    edges = rows("MATCH (a)-[r]->(b) RETURN a.id, type(r), b.id LIMIT 45")
    expected_edges = {(r.source_id, r.rel_type, r.target_id) for r in relationships}
    if len(edges) != 44 or {tuple(row) for row in edges} != expected_edges:
        raise ValueError("Persisted directed relationships mismatch")
    if rows("MATCH (d {id:'decision:D-007'}) RETURN d.status") != [["accepted"]]:
        raise ValueError("Accepted D-007 missing")
    ids = list(dict.fromkeys(chunk.source_id for chunk in chunks))
    sources = find_sources(ids, adapter=adapter)
    if [s.id for s in sources] != ids:
        raise ValueError("Persisted source retrieval incomplete")
    for source in sources:
        expected = sorted((c for c in chunks if c.source_id == source.id), key=lambda c: (c.chunk_index, c.id))
        if (source.chunk_ids != [c.id for c in expected]
                or source.snippet != "\n\n".join(c.text.strip() for c in expected)):
            raise ValueError("Persisted source provenance/text mismatch")


def bootstrap(expected_pid):
    from redis import Redis
    from redis.backoff import NoBackoff
    from redis.retry import Retry
    from weave_data.graph_adapter import FalkorDBGraphAdapter
    from weave_data.ingest import prepare_ingestion, run_ingestion

    runtime_environment(os.environ)  # Refuse external settings even if invoked separately.
    if expected_pid <= 1:
        raise ValueError("Owned database PID required")
    client = Redis(host="127.0.0.1", port=6379, socket_connect_timeout=1, socket_timeout=1,
                   retry=Retry(NoBackoff(), 0))
    try:
        wait_for_owned_graph(client, expected_pid)
    finally:
        client.close()
    data = ROOT / "data" / "novapay"
    records, relationships, chunks, aliases, validation = prepare_ingestion(data)
    if not validation.ok or (len(records), len(chunks), len(relationships), len(aliases)) != (20, 6, 44, 29):
        raise ValueError("Approved dataset preparation mismatch")
    adapter = FalkorDBGraphAdapter(host="127.0.0.1", port=6379, graph_name="novapay",
                                   ssl=False, socket_connect_timeout=2, socket_timeout=5)
    try:
        result = run_ingestion(data, adapter)
        if result.status != "success" or result.errors:
            raise ValueError("Local demo ingestion failed")
        verify_seed(adapter, records, relationships, chunks)
        print("Render demo seed verified: 20 entities, 6 chunks, 44 relationships; persisted sources verified",
              flush=True)
    finally:
        adapter.close()


if __name__ == "__main__":
    try:
        bootstrap(int(sys.argv[1]))
    except Exception:
        print("Render demo bootstrap rejected: local graph ownership, readiness or seed validation failed.",
              file=sys.stderr, flush=True)
        raise SystemExit(1) from None
