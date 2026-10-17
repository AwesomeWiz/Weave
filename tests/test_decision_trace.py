from weave_graph.trace import trace_decision


def test_trace_decision_missing_service_returns_warning():
    class FakeResult:
        result_set = []

    class FakeClient:
        def execute(self, query, params=None):
            return FakeResult()

    result = trace_decision(
        FakeClient(),
        service_id="service:missing",
        technology_id="tech:redis",
    )

    assert result["data"]["decision"] is None
    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["warnings"]


def test_trace_decision_returns_expected_structure():
    expected_keys = {"data", "sources", "nodes", "edges", "warnings"}

    class FakeResult:
        result_set = []

    class FakeClient:
        def execute(self, query, params=None):
            return FakeResult()

    result = trace_decision(FakeClient())

    assert set(result.keys()) == expected_keys
    assert result["warnings"]
