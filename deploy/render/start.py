"""Supervise an owned, disposable local FalkorDB and one API worker.

Only used by the experimental Render image. No shell expansion or external DB
selection; no application API, query, fixture or evidence contracts are changed.
"""
import json
from contextlib import suppress
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
POLICY = "novapay-disposable-v1"
LOCAL = {
    "WEAVE_GRAPH_MODE": "falkordb", "WEAVE_GRAPH_NAME": "novapay",
    "WEAVE_GRAPH_FACTORY": "app.antony:create_gateway", "WEAVE_SOURCE_BACKEND": "weave_data",
    "WEAVE_FALKORDB_HOST": "127.0.0.1", "WEAVE_FALKORDB_PORT": "6379",
    "WEAVE_FALKORDB_SSL": "false", "WEAVE_FALKORDB_USERNAME": "", "WEAVE_FALKORDB_PASSWORD": "",
    "WEAVE_LLM_PROVIDER": "none",
}
MODULE = "/var/lib/falkordb/bin/falkordb.so"


def runtime_environment(environ):
    env = dict(environ)
    if env.get("WEAVE_DEMO_BOOTSTRAP") != POLICY:
        raise ValueError("Explicit disposable demo bootstrap policy required")
    for key, value in LOCAL.items():
        if env.get(key, value) != value:
            raise ValueError(f"Render demo requires local-only setting: {key}")
        env[key] = value
    port = env.get("PORT", "10000")
    if not port.isascii() or not port.isdecimal() or not 1024 <= int(port) <= 65535 or int(port) == 6379:
        raise ValueError("Invalid public API port")
    origins = json.loads(env.get("WEAVE_CORS_ORIGINS", "[]"))
    if not isinstance(origins, list) or not origins:
        raise ValueError("Configure exact HTTPS frontend origins")
    for origin in origins:
        if not isinstance(origin, str):
            raise ValueError("Invalid frontend origin")
        url = urlsplit(origin)
        if (url.scheme != "https" or not url.hostname or "*" in origin or url.username or url.password
                or url.path or url.query or url.fragment):
            raise ValueError("Only exact HTTPS frontend origins are allowed")
    env.update(PORT=port, PYTHONPATH=f"{ROOT / 'backend'}{os.pathsep}{ROOT}",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MALLOC_ARENA_MAX="2")
    return env


def redis_command(directory):
    return [
        "redis-server", "--bind", "127.0.0.1", "--port", "6379", "--protected-mode", "yes",
        "--daemonize", "no", "--dir", str(directory), "--save", "", "--appendonly", "no",
        "--maxmemory", "192mb", "--maxmemory-policy", "noeviction", "--maxclients", "32",
        "--loadmodule", MODULE, "THREAD_COUNT", "1", "OMP_THREAD_COUNT", "1",
        "NODE_CREATION_BUFFER", "128", "CACHE_SIZE", "10", "MAX_QUEUED_QUERIES", "8",
        "QUERY_MEM_CAPACITY", "33554432", "TIMEOUT_DEFAULT", "5000", "TIMEOUT_MAX", "10000",
        "BOLT_PORT", "-1",
    ]


def api_command(port):
    return [sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "backend",
            "--host", "0.0.0.0", "--port", port, "--workers", "1", "--limit-concurrency", "4",
            "--backlog", "16", "--timeout-graceful-shutdown", "8", "--no-access-log"]


def stop_children(children):
    # Signal whole owned process groups; tini also reaps orphaned descendants.
    for child in reversed(children):
        if child.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    for child in reversed(children):
        try:
            child.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=2)


def supervise(env, directory, stopping):
    children = []
    try:
        if stopping():
            return 0
        db = subprocess.Popen(redis_command(directory), cwd=ROOT, env=env, start_new_session=True)
        children.append(db)
        seed = subprocess.Popen([sys.executable, "deploy/render/bootstrap.py", str(db.pid)],
                                cwd=ROOT, env=env, start_new_session=True)
        children.append(seed)
        deadline = time.monotonic() + 120
        while seed.poll() is None:
            if stopping():
                return 0
            if db.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("Local graph/bootstrap did not become ready")
            time.sleep(0.2)
        if stopping():
            return 0
        if seed.returncode != 0 or db.poll() is not None:
            raise RuntimeError("Local graph/bootstrap failed")
        api = subprocess.Popen(api_command(env["PORT"]), cwd=ROOT, env=env, start_new_session=True)
        children.append(api)
        print("Render demo: real local graph seeded; starting one API worker", flush=True)
        while not stopping():
            if db.poll() is not None or api.poll() is not None:
                raise RuntimeError("A required demo process stopped")
            time.sleep(0.2)
        return 0
    finally:
        stop_children(children)


def main():
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        env = runtime_environment(os.environ)
        # Fresh owned directory each boot; never load or reset an existing graph.
        with tempfile.TemporaryDirectory(prefix="weave-render-") as directory:
            return supervise(env, directory, lambda: stopping)
    except Exception:
        print("Render demo startup/runtime failed; API stopped. Check policy, image and local graph readiness.",
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
