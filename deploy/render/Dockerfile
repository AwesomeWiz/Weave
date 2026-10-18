# Experimental single-service demo. Render builds this; no local Docker needed.
# Versioned official server-only image: no FalkorDB Browser/Node service.
FROM falkordb/falkordb-server:v4.22.0

USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv tini \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/weave-venv
ENV PATH="/opt/weave-venv/bin:$PATH" \
    PYTHONPATH="/srv/weave/backend:/srv/weave" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 \
    WEAVE_GRAPH_MODE=falkordb WEAVE_GRAPH_NAME=novapay \
    WEAVE_GRAPH_FACTORY=app.antony:create_gateway WEAVE_SOURCE_BACKEND=weave_data \
    WEAVE_FALKORDB_HOST=127.0.0.1 WEAVE_FALKORDB_PORT=6379 WEAVE_FALKORDB_SSL=false \
    WEAVE_FALKORDB_USERNAME="" WEAVE_FALKORDB_PASSWORD="" WEAVE_LLM_PROVIDER=none

WORKDIR /srv/weave
RUN python -c "import sys; assert sys.version_info >= (3, 11); print('Image Python:', sys.version.split()[0])"
COPY backend/requirements.lock.txt backend/requirements.lock.txt
COPY deploy/render/requirements.txt deploy/render/requirements.txt
# Resolve production roots transitively, retaining the existing version pins.
RUN python -m pip install --no-cache-dir -c backend/requirements.lock.txt -r deploy/render/requirements.txt \
    && python -m pip check
COPY --chown=10001:10001 backend/app backend/app
COPY --chown=10001:10001 app/graph app/graph
COPY --chown=10001:10001 weave_graph weave_graph
COPY --chown=10001:10001 weave_data weave_data
COPY --chown=10001:10001 data/novapay data/novapay
COPY --chown=10001:10001 deploy/render deploy/render
# Fail the build on a missing module dependency or application import collision.
RUN python -c "import subprocess; p='/var/lib/falkordb/bin/falkordb.so'; out=subprocess.check_output(['ldd', p], text=True); assert 'not found' not in out; from app.main import app; from weave_graph.trace import trace_decision; from weave_graph.impact import impact_analysis; from weave_graph.experts import find_expert; from weave_graph.freshness import find_stale_knowledge; from weave_data.ingest import prepare_ingestion; assert prepare_ingestion()[-1].ok"

USER 10001:10001
EXPOSE 10000
STOPSIGNAL SIGTERM
# Replace upstream startup (which is not our process supervisor).
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "deploy/render/start.py"]
