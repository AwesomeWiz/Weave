"""Keep offline tests independent of an operator's hosted-provider .env."""
import pytest


@pytest.fixture(autouse=True)
def offline_provider_default(monkeypatch):
    # Tests exercising providers select one explicitly and mock their transport.
    # Never inherit a real hosted key/provider combination from local settings.
    monkeypatch.setenv("WEAVE_LLM_PROVIDER", "none")
