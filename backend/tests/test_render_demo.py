"""Offline Render startup/seed checks. Doubles do not prove container feasibility."""
from importlib import metadata
from pathlib import Path
import signal
from types import SimpleNamespace

from packaging.markers import default_environment
from packaging.requirements import Requirement
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError, ResponseError

from deploy.render import bootstrap as seed
from deploy.render import start
from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import prepare_ingestion, run_ingestion

ROOT = Path(__file__).resolve().parents[2]


def environment(**overrides):
    return {"WEAVE_DEMO_BOOTSTRAP": start.POLICY,
            "WEAVE_CORS_ORIGINS": '["https://weave-demo.vercel.app"]', **overrides}


def test_explicit_policy_is_required_before_any_process(monkeypatch):
    monkeypatch.delenv("WEAVE_DEMO_BOOTSTRAP", raising=False)
    monkeypatch.setattr(start.subprocess, "Popen", lambda *_a, **_k: pytest.fail("Process started"))
    assert start.main() == 1


def test_local_real_mode_and_single_worker_commands():
    env = start.runtime_environment(environment(PORT="10001"))
    assert all(env[k] == v for k, v in start.LOCAL.items())
    assert env["OMP_NUM_THREADS"] == "1"
    cmd = start.redis_command("/tmp/owned-demo")
    assert cmd[cmd.index("--bind") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--dir") + 1] == "/tmp/owned-demo"
    assert cmd[cmd.index("--maxmemory-policy") + 1] == "noeviction"
    assert cmd[cmd.index("--save") + 1] == ""
    assert cmd[cmd.index("--appendonly") + 1] == "no"
    assert cmd[cmd.index("BOLT_PORT") + 1] == "-1"
    assert not any("flush" in arg.lower() or "reset" in arg.lower() for arg in cmd)
    api = start.api_command(env["PORT"])
    assert api[api.index("--workers") + 1] == "1"
    assert api[api.index("--host") + 1] == "0.0.0.0"
    assert api[api.index("--port") + 1] == "10001"
    assert api[api.index("--app-dir") + 1] == "backend"


@pytest.mark.parametrize("key,value", [
    ("WEAVE_GRAPH_MODE", "fixture"), ("WEAVE_GRAPH_NAME", "shared"),
    ("WEAVE_GRAPH_FACTORY", "other:factory"), ("WEAVE_SOURCE_BACKEND", "delegate"),
    ("WEAVE_FALKORDB_HOST", "external.example.org"), ("WEAVE_FALKORDB_PORT", "6380"),
    ("WEAVE_FALKORDB_PASSWORD", "must-not-be-printed"), ("WEAVE_FALKORDB_SSL", "true"),
    ("WEAVE_LLM_PROVIDER", "openrouter"), ("PORT", "6379"), ("PORT", "0"),
    ("PORT", "65536"), ("PORT", "10000;bad"), ("WEAVE_DEMO_BOOTSTRAP", "yes"),
    ("WEAVE_CORS_ORIGINS", '[]'), ("WEAVE_CORS_ORIGINS", '["*"]'),
    ("WEAVE_CORS_ORIGINS", '["https://user:password@example.org"]'),
])
def test_unsafe_or_external_configuration_fails_closed(key, value):
    with pytest.raises(ValueError) as error:
        start.runtime_environment(environment(**{key: value}))
    assert "must-not-be-printed" not in str(error.value)
    assert "user:password" not in str(error.value)


@pytest.mark.parametrize("failure", ["pid", "graphs", "module"])
def test_readiness_refuses_foreign_process_existing_graph_and_plain_redis(failure):
    probe = SimpleNamespace(ping=lambda: True,
                            info=lambda _: {"process_id": 99 if failure == "pid" else 100})
    def command(_):
        if failure == "module":
            raise ResponseError("unknown command GRAPH.LIST")
        return ["novapay"] if failure == "graphs" else []
    probe.execute_command = command
    with pytest.raises((ValueError, ResponseError)):
        seed.wait_for_owned_graph(probe, 100)


def test_readiness_retries_connection_only_and_has_a_deadline(monkeypatch):
    ticks = iter([0, 0, 1, 2, 3])
    monkeypatch.setattr(seed.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(seed.time, "sleep", lambda _: None)
    attempts = []
    def ping():
        attempts.append(True)
        raise RedisConnectionError("not ready")
    with pytest.raises(RuntimeError, match="deadline"):
        seed.wait_for_owned_graph(SimpleNamespace(ping=ping), 100, timeout=3)
    assert len(attempts) == 3


class OfflineReadbackStore(InMemoryGraphAdapter):
    """Explicit test-only persistence and readback double, never a runtime mode."""
    def __init__(self, **kwargs):
        super().__init__()
        assert kwargs["host"] == "127.0.0.1" and kwargs["graph_name"] == "novapay"
        self._graph = SimpleNamespace(ro_query=self.read)
        self.closed = False

    def close(self):
        self.closed = True

    def read(self, query, **_kwargs):
        if "RETURN n.id" in query:
            rows = [[key] for key in self._nodes]
        elif "RETURN count(c)" in query:
            rows = [[len(self._chunks)]]
        elif "RETURN a.id" in query:
            rows = [[r["source_id"], r["rel_type"], r["target_id"]] for r in self._relationships.values()]
        elif "RETURN d.status" in query:
            rows = [[self._nodes["decision:D-007"]["status"]]]
        else:
            pytest.fail(f"Unexpected readback query: {query}")
        return SimpleNamespace(result_set=rows)


def prepared_store():
    prepared = prepare_ingestion(ROOT / "data" / "novapay")
    store = OfflineReadbackStore(host="127.0.0.1", graph_name="novapay")
    assert run_ingestion(ROOT / "data" / "novapay", store).status == "success"
    return store, prepared


def test_seed_readback_checks_exact_inventory_direction_status_and_chunks():
    store, (records, edges, chunks, _, validation) = prepared_store()
    assert validation.ok
    seed.verify_seed(store, records, edges, chunks)
    expected = {(r.source_id, r.rel_type, r.target_id) for r in edges}
    assert {
        ("decision:D-007", "IMPLEMENTED_BY", "commit:8fae2"),
        ("commit:8fae2", "CHANGES", "service:payment-service"),
        ("service:payment-service", "USES", "tech:redis"),
        ("service:checkout-service", "DEPENDS_ON", "service:payment-service"),
        ("service:order-service", "DEPENDS_ON", "service:checkout-service"),
    } <= expected


@pytest.mark.parametrize("damage", ["node", "direction", "status", "chunk", "text"])
def test_corrupt_seed_is_rejected_without_reset_or_substitution(damage):
    store, (records, edges, chunks, _, _) = prepared_store()
    if damage == "node":
        store._nodes.pop("service:payment-service")
    elif damage == "direction":
        edge = next(r for r in store._relationships.values() if r["rel_type"] == "USES")
        edge["source_id"], edge["target_id"] = edge["target_id"], edge["source_id"]
    elif damage == "status":
        store._nodes["decision:D-007"]["status"] = "proposed"
    elif damage == "chunk":
        store._chunks.pop("chunk:issue:PAY-42:0")
    else:
        store._chunks["chunk:issue:PAY-42:0"]["text"] = "unapproved replacement"
    with pytest.raises(ValueError):
        seed.verify_seed(store, records, edges, chunks)


def test_bootstrap_uses_real_adapter_boundary_and_closes_it(monkeypatch):
    import redis
    import weave_data.graph_adapter as adapters
    monkeypatch.setenv("WEAVE_DEMO_BOOTSTRAP", start.POLICY)
    monkeypatch.setenv("WEAVE_CORS_ORIGINS", '["https://weave-demo.vercel.app"]')
    for key, value in start.LOCAL.items():
        monkeypatch.setenv(key, value)
    probe = SimpleNamespace(ping=lambda: True, info=lambda _: {"process_id": 100},
                            execute_command=lambda _: [], close=lambda: None)
    monkeypatch.setattr(redis, "Redis", lambda **_: probe)
    stores = []
    def adapter(**kwargs):
        stores.append(OfflineReadbackStore(**kwargs))
        return stores[-1]
    monkeypatch.setattr(adapters, "FalkorDBGraphAdapter", adapter)
    seed.bootstrap(100)
    assert len(stores) == 1 and stores[0].closed


@pytest.mark.parametrize("phase", ["seed_failure", "db_failure", "bootstrap_timeout", "api_exit", "db_exit", "signal"])
def test_supervisor_startup_runtime_failure_and_shutdown(monkeypatch, phase):
    children, commands, stopped = [], [], []
    db_checks = []
    class Process:
        def __init__(self, command, **kwargs):
            self.kind = len(children)
            self.pid = 100 + self.kind
            self.returncode = None
            assert kwargs["start_new_session"] is True
            children.append(self)
            commands.append(command)

        def poll(self):
            if self.kind == 0:
                db_checks.append(True)
                if phase == "db_failure" or (phase == "db_exit" and len(children) == 3):
                    return 1
            elif self.kind == 1 and phase != "bootstrap_timeout":
                self.returncode = 1 if phase == "seed_failure" else 0
                return self.returncode
            elif self.kind == 2 and phase == "api_exit":
                return 0  # Even an unexpected successful child exit stops service.
            return None

    monkeypatch.setattr(start.subprocess, "Popen", Process)
    monkeypatch.setattr(start, "stop_children", lambda processes: stopped.extend(processes))
    monkeypatch.setattr(start.time, "sleep", lambda _: None)
    ticks = iter([0, 121])
    if phase == "bootstrap_timeout":
        monkeypatch.setattr(start.time, "monotonic", lambda: next(ticks))
    def stopping():
        return phase == "signal" and len(children) == 3
    if phase == "signal":
        assert start.supervise(start.runtime_environment(environment()), "/tmp/owned-demo", stopping) == 0
    else:
        with pytest.raises(RuntimeError):
            start.supervise(start.runtime_environment(environment()), "/tmp/owned-demo", stopping)
    assert stopped == children
    assert len(children) == (3 if phase in {"api_exit", "db_exit", "signal"} else 2)


def test_cleanup_signals_owned_children_and_escalates_after_deadline(monkeypatch):
    events = []
    class Process:
        pid = 100
        attempts = 0
        def poll(self):
            return None
        def wait(self, timeout):
            self.attempts += 1
            if self.attempts == 1:
                raise start.subprocess.TimeoutExpired("test-owned-child", timeout)
    monkeypatch.setattr(start.os, "killpg", lambda pid, sig: events.append((pid, sig)), raising=False)
    monkeypatch.setattr(start.signal, "SIGKILL", 9, raising=False)  # Mock POSIX behavior on Windows.
    start.stop_children([Process()])
    assert events == [(100, signal.SIGTERM), (100, signal.SIGKILL)]


def test_production_dependency_closure_keeps_required_pins_without_test_packages():
    # Inspect real installed distribution metadata, using Linux markers for the
    # apt Python target. Docker also runs pip check and imports all four tools.
    pins = {name.lower().replace("_", "-"): version for name, version in
            (line.split("==") for line in (ROOT / "backend/requirements.lock.txt").read_text().splitlines())}
    roots = [line for line in (ROOT / "deploy/render/requirements.txt").read_text().splitlines()
             if line and not line.startswith("#")]
    backend_roots = {Requirement(line).name.lower() for line in (ROOT / "backend/requirements.txt").read_text().splitlines() if line}
    assert set(roots) == backend_roots - {"pytest", "ruff"}
    env = {**default_environment(), "sys_platform": "linux", "platform_system": "Linux",
           "os_name": "posix", "python_version": "3.13", "python_full_version": "3.13.0", "extra": ""}
    visited, pending = set(), list(roots)
    while pending:
        name = pending.pop().lower().replace("_", "-")
        if name in visited:
            continue
        visited.add(name)
        assert metadata.version(name) == pins[name]
        for value in metadata.requires(name) or []:
            requirement = Requirement(value)
            if requirement.marker is None or requirement.marker.evaluate(env):
                assert metadata.version(requirement.name) in requirement.specifier
                pending.append(requirement.name)
    assert not {"pytest", "ruff", "pluggy", "iniconfig", "pygments"} & visited


def test_container_keeps_upstream_binary_libraries_and_isolates_context():
    dockerfile = (ROOT / "deploy/render/Dockerfile").read_text()
    assert "FROM falkordb/falkordb-server:v4.22.0" in dockerfile
    assert "-c backend/requirements.lock.txt" in dockerfile and "pip check" in dockerfile
    assert "USER 10001:10001" in dockerfile and "tini" in dockerfile
    assert 'CMD ["python", "deploy/render/start.py"]' in dockerfile
    assert "COPY . " not in dockerfile and "EXPOSE 6379" not in dockerfile
    ignore = (ROOT / "deploy/render/Dockerfile.dockerignore").read_text()
    assert "**/.env" in ignore and "!data/novapay/**" in ignore
