import asyncio
import time

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .context import build_context
from .context_v2 import CombinedContext
from .graph import FalkorGateway, GraphContractError, GraphGateway, GraphUnavailable, create_gateway
from .llm import LLMProvider, create_provider
from .impact import build_impact_context
from .experts import build_expert_context
from .freshness import build_freshness_context
from .models import ExpertInput, ExpertResponse, FreshnessInput, FreshnessResponse, HealthResponse, ImpactInput, ImpactResponse, Metadata, QueryRequest, QueryResponse
from .orchestration import TOOL_REGISTRY, execute_plan
from .router import plan_question, route_question
from .synthesis import single_tool_context


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
        if _request.url.path == "/api/tools/freshness":
            return error_response("INVALID_REQUEST", "Enter an exact entity name or canonical ID of 1–256 characters.", 422)
        if _request.url.path == "/api/tools/expert-finder":
            return error_response("INVALID_REQUEST", "Enter a nonblank query of 1–2,000 characters "
                                  "and an integer limit between 1 and 10.", 422)
        if _request.url.path == "/api/tools/impact-analysis":
            return error_response("INVALID_REQUEST", "Use a canonical service: or tech: entity ID "
                                  "and an integer max_depth between 1 and 3.", 422)
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

    async def hosted_answer(question, context, metadata, tool=None, data=None):
        if config.llm_provider != "openrouter" or context.status == "insufficient_evidence":
            return context.summary
        try:
            packet = context if isinstance(context, CombinedContext) else single_tool_context(context, tool, data)
            answer = await llm.generate(question, packet)
            metadata.generation = "openrouter"
            return answer
        except Exception:
            metadata.warnings.append("OpenRouter synthesis unavailable or rejected; showing the deterministic evidence summary.")
            return context.summary

    async def run_impact(request: ImpactInput, question: str | None = None) -> ImpactResponse:
        start = time.perf_counter()
        result = await graph.impact_analysis(request)
        try:
            records = await graph.find_sources(list(dict.fromkeys(s.id for s in result.sources)))
        except GraphUnavailable:
            records = []
            result.warnings.append("Source retrieval is unavailable; graph evidence was retained.")
        context, data = build_impact_context(result, records, request)
        if config.graph_mode == "fixture":
            context.warnings.insert(0, "Development fixture — synthetic evidence, not live FalkorDB data.")
        metadata = Metadata(latency_ms=0, graph_mode=config.graph_mode, warnings=context.warnings)
        answer = await hosted_answer(question or f"What could be affected by changes to {request.entity_id}?",
                                     context, metadata, "impact_analysis", data)
        metadata.latency_ms = round((time.perf_counter() - start) * 1000)
        return ImpactResponse(
            answer=answer, support_status=context.status, tools_used=["impact_analysis"],
            sources=context.sources, graph=context.graph, data=data,
            metadata=metadata,
        )

    @app.post("/api/tools/impact-analysis", response_model=ImpactResponse)
    async def impact_analysis(request: ImpactInput):
        return await run_impact(request)

    async def run_expert(request: ExpertInput) -> ExpertResponse:
        start = time.perf_counter()
        result = await graph.find_expert(request)
        try:
            records = await graph.find_sources(list(dict.fromkeys(s.id for s in result.sources)))
        except GraphUnavailable:
            records = []
            result.warnings.append("Source retrieval is unavailable; graph evidence was retained.")
        context, data = build_expert_context(result, records, request)
        if config.graph_mode == "fixture":
            context.warnings.insert(0, "Development fixture — synthetic evidence, not live FalkorDB data.")
        metadata = Metadata(latency_ms=0, graph_mode=config.graph_mode, warnings=context.warnings)
        answer = await hosted_answer(request.query, context, metadata, "find_expert")
        metadata.latency_ms = round((time.perf_counter() - start) * 1000)
        return ExpertResponse(answer=answer, support_status=context.status, tools_used=["find_expert"],
                              sources=context.sources, graph=context.graph, metadata=metadata, data=data)

    @app.post("/api/tools/expert-finder", response_model=ExpertResponse)
    async def expert_finder(request: ExpertInput):
        return await run_expert(request)

    async def run_freshness(request: FreshnessInput) -> FreshnessResponse:
        start = time.perf_counter()
        result = await graph.find_stale_knowledge(request)
        try:
            records = await graph.find_sources(list(dict.fromkeys(s.id for s in result.sources)))
        except GraphUnavailable:
            records = []
            result.warnings.append("Source retrieval is unavailable; graph evidence was retained.")
        context, data = build_freshness_context(result, records, request)
        if config.graph_mode == "fixture":
            context.warnings.insert(0, "Development fixture — synthetic evidence, not live FalkorDB data.")
        metadata = Metadata(latency_ms=0, graph_mode=config.graph_mode, warnings=context.warnings)
        answer = await hosted_answer(f"Which documents about {request.entity} need review?",
                                     context, metadata, "find_stale_knowledge")
        metadata.latency_ms = round((time.perf_counter() - start) * 1000)
        return FreshnessResponse(answer=answer, support_status=context.status, tools_used=["find_stale_knowledge"],
                                 sources=context.sources, graph=context.graph, metadata=metadata, data=data)

    @app.post("/api/tools/freshness", response_model=FreshnessResponse)
    async def freshness(request: FreshnessInput):
        return await run_freshness(request)

    @app.post("/api/query", response_model=QueryResponse)
    async def query(request: QueryRequest):
        start = time.perf_counter()
        metadata = Metadata(latency_ms=0, graph_mode=config.graph_mode)
        plan = plan_question(request.question)
        target = route_question(request.question)
        if len(plan.calls) == 1 and plan.calls[0].name == "find_stale_knowledge" and not plan.limitations and not plan.composite:
            response = await run_freshness(FreshnessInput.model_validate(plan.calls[0].arguments.model_dump()))
            return QueryResponse.model_validate(response.model_dump(exclude={"data"}))
        if len(plan.calls) == 1 and plan.calls[0].name == "find_expert" and not plan.limitations and not plan.composite:
            response = await run_expert(ExpertInput.model_validate(plan.calls[0].arguments.model_dump()))
            return QueryResponse.model_validate(response.model_dump(exclude={"data"}))
        if (plan.composite or plan.limitations or target is None
                or any(call.name not in TOOL_REGISTRY for call in plan.calls)):
            context, tools_used = await execute_plan(plan, graph)
            metadata.warnings = context.warnings
            if config.graph_mode == "fixture":
                metadata.warnings.insert(0, "Development fixture — synthetic evidence, not live FalkorDB data.")
            answer = await hosted_answer(request.question, context, metadata)
            metadata.latency_ms = round((time.perf_counter() - start) * 1000)
            return QueryResponse(answer=answer, support_status=context.status,
                                 tools_used=tools_used, sources=context.sources,
                                 graph=context.graph, metadata=metadata)
        if isinstance(target, ImpactInput):
            response = await run_impact(target, request.question)
            return QueryResponse.model_validate(response.model_dump(exclude={"data"}))
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
        if config.llm_provider == "openrouter":
            answer = await hosted_answer(request.question, context, metadata, "decision_trace")
        elif context.can_explain and config.llm_provider == "ollama":
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
