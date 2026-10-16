import asyncio
import time

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .context import build_context
from .graph import FalkorGateway, GraphContractError, GraphGateway, GraphUnavailable, create_gateway
from .llm import LLMProvider, create_provider
from .models import HealthResponse, Metadata, QueryRequest, QueryResponse
from .router import route_question


def error_response(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={
        "ok": False, "error": {"code": code, "message": message},
    })


def create_app(settings: Settings | None = None, gateway: GraphGateway | None = None,
               provider: LLMProvider | None = None) -> FastAPI:
    config = settings or Settings()
    graph = gateway or create_gateway(config)
    llm = provider or create_provider(config)
    app = FastAPI(title="Weave", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _error):
        return error_response("INVALID_REQUEST", "Enter a question of 1–2,000 characters; "
                              "session_id must be at most 128 characters.", 422)

    @app.exception_handler(GraphUnavailable)
    async def unavailable(_request, _error):
        return error_response("GRAPH_UNAVAILABLE", "The graph integration is unavailable. "
                              "Configure WEAVE_GRAPH_FACTORY and a seeded FalkorDB instance, "
                              "or explicitly select development fixture mode.", 503)

    @app.exception_handler(GraphContractError)
    async def invalid_graph(_request, _error):
        return error_response("GRAPH_CONTRACT_ERROR", "The graph tool returned invalid evidence. "
                              "Check the integration adapter's node, edge and source contract.", 502)

    @app.exception_handler(Exception)
    async def unexpected(_request, _error):
        return error_response("INTERNAL_ERROR", "Weave could not complete this request. "
                              "Please retry or check the backend configuration.", 500)

    @app.get("/api/health", response_model=HealthResponse)
    async def health():
        graph_probe, llm_probe = await asyncio.gather(
            graph.health(), llm.availability(), return_exceptions=True,
        )
        ready = graph_probe is True
        llm_state = (llm_probe if isinstance(llm_probe, str)
                     and llm_probe in {"available", "unavailable", "disabled"} else "unavailable")
        db_state = "not_checked"
        if config.graph_mode == "falkordb":
            connected = await graph.database_health() if isinstance(graph, FalkorGateway) else ready
            db_state = "connected" if connected else "unavailable"
        critical = config.graph_mode == "falkordb" and (not ready or db_state != "connected")
        result = HealthResponse(
            status="unavailable" if critical else (
                "degraded" if config.graph_mode == "fixture" or llm_state == "unavailable" else "ok"
            ),
            falkordb=db_state, graph_tool=("fixture" if config.graph_mode == "fixture" else
                                         "available" if ready else "unavailable"),
            llm=llm_state, graph=config.graph_name, graph_mode=config.graph_mode,
        )
        return JSONResponse(status_code=503 if critical else 200, content=result.model_dump())

    @app.post("/api/query", response_model=QueryResponse)
    async def query(request: QueryRequest):
        start = time.perf_counter()
        metadata = Metadata(latency_ms=0, graph_mode=config.graph_mode)
        target = route_question(request.question)
        if not target:
            metadata.latency_ms = round((time.perf_counter() - start) * 1000)
            return QueryResponse(
                answer="Phase 1 traces the Payment Service / Redis decision. "
                       "Try: Why does Payment Service use Redis? "
                       "Other questions do not yet have a supported retrieval route.",
                support_status="insufficient_evidence", tools_used=[], metadata=metadata,
            )
        trace = await graph.trace_decision(target)
        try:
            records = await graph.find_sources(trace.source_ids)
        except GraphUnavailable:
            records = []
            trace.warnings.append("Source retrieval is unavailable; graph evidence was retained.")
        context = build_context(trace, records, target)
        answer = context.summary
        metadata.warnings = context.warnings
        if config.graph_mode == "fixture":
            metadata.warnings.insert(0, "Development fixture — synthetic evidence, not live FalkorDB data.")
        if context.can_explain and config.llm_provider != "none":
            try:
                answer = await llm.generate(request.question, context)
                metadata.generation = "ollama"
            except Exception:
                metadata.warnings.append("LLM generation unavailable; showing the graph-grounded summary.")
        metadata.latency_ms = round((time.perf_counter() - start) * 1000)
        return QueryResponse(answer=answer, support_status=context.status,
                             tools_used=["trace_decision"], sources=context.sources,
                             graph=context.graph, metadata=metadata)

    return app


app = create_app()
