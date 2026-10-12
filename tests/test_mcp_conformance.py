"""Conformance with the Model Context Protocol, revision 2026-07-28.

Nothing in this project's documents required this until 2026-10-11 — not
CLAUDE.md, not .claude/rules/security.md, not MCP-SECURITY-FRAMEWORK.md, not
qso-graph-spec. We documented how to *publish* an MCP server in detail and
never wrote down what makes one *valid*, which is how a missing ``isError`` and
missing annotations reached all 22 servers in the fleet unnoticed.

So these are asserted rather than trusted.

What is particular to this server is not credentials — it has none — but that
it was **reporting the wrong fact**. ``summit_info`` caught every ``RuntimeError``
from the fetch and answered ``{"error": "Not found"}``, so SOTA being
unreachable, SOTA answering 500, and a summit genuinely not existing all came
back identically. A caller told "no such summit" during an outage concludes the
summit does not exist. ``TestAnOutageIsNotAnAbsence`` is the point of this file.

Test IDs: SOTA-C01 onward.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastmcp.exceptions import ToolError

os.environ["SOTA_MCP_MOCK"] = "1"

from sota_mcp import server  # noqa: E402

ANNOTATION_HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")

READS_SOTA = {"sota_spots", "sota_alerts", "sota_summit_info", "sota_summits_near"}
ANSWERS_FROM_THE_PACKAGE = {"get_version_info"}


def _tools() -> dict[str, object]:
    return {t.name: t for t in asyncio.run(server.mcp.list_tools())}


def _wire(tool: object) -> dict[str, object]:
    """The serialised annotations, which is what a client reads."""
    annotations = getattr(tool, "annotations", None)
    assert annotations is not None, "tool declares no annotations"
    return annotations.model_dump(by_alias=True, exclude_none=True)


def _call(name: str):
    """The underlying function of a registered tool."""
    tool = getattr(server, name)
    return getattr(tool, "fn", tool)


class TestToolAnnotations:
    def test_every_tool_declares_all_four_hints(self) -> None:
        """SOTA-C01: the defaults are pessimistic, so silence is the wrong answer."""
        for name, tool in _tools().items():
            wire = _wire(tool)
            for hint in ANNOTATION_HINTS:
                assert hint in wire, f"{name} omits {hint} on the wire; got {sorted(wire)}"

    def test_every_tool_reads_and_none_writes(self) -> None:
        """SOTA-C02: nothing is written, and this server holds no credential at all."""
        for name, tool in _tools().items():
            wire = _wire(tool)
            assert wire["readOnlyHint"] is True, name
            assert wire["destructiveHint"] is False, name
            assert wire["idempotentHint"] is True, name

    def test_open_world_is_read_per_tool(self) -> None:
        """SOTA-C03: four reach api2.sota.org.uk; one does not."""
        tools = _tools()
        assert set(tools) == READS_SOTA | ANSWERS_FROM_THE_PACKAGE
        for name in READS_SOTA:
            assert _wire(tools[name])["openWorldHint"] is True, name
        for name in ANSWERS_FROM_THE_PACKAGE:
            assert _wire(tools[name])["openWorldHint"] is False, name


class TestAnOutageIsNotAnAbsence:
    """The defect this repo actually had.

    ``summit_info`` wrapped the fetch in ``except RuntimeError: data = None``
    and then answered ``{"summitCode": ..., "error": "Not found"}``. Three
    different facts arrived as one, and the one reported was wrong for two of
    them:

    * SOTA unreachable → "Not found"
    * SOTA answering 500 → "Not found"
    * the summit genuinely absent → "Not found"

    The catch was doing real work — SOTA answers 404 for an unknown summit —
    so the fix is to tell 404 apart from the rest, not to delete it.
    """

    def _client(self, monkeypatch):
        from sota_mcp.client import SOTAClient

        monkeypatch.delenv("SOTA_MCP_MOCK", raising=False)
        client = SOTAClient()
        monkeypatch.setattr(server, "_get_client", lambda: client)
        return client

    def test_an_unreachable_api_says_the_request_failed(self, monkeypatch) -> None:
        """SOTA-C10: not "no such summit"."""
        import urllib.error
        import urllib.request

        self._client(monkeypatch)
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(
            urllib.error.URLError("Connection refused")))
        with pytest.raises(ToolError) as caught:
            _call("sota_summit_info")(summit_code="W7A/MN-001")
        message = str(caught.value)
        assert "request failed" in message
        assert "no summit" not in message, "an outage was reported as an absence"

    def test_a_server_error_says_the_request_failed(self, monkeypatch) -> None:
        """SOTA-C11: a 500 is SOTA's problem, not evidence about the summit."""
        import urllib.error
        import urllib.request

        self._client(monkeypatch)

        def boom(*_a, **_k):
            raise urllib.error.HTTPError("u", 500, "Server Error", {}, None)  # type: ignore[arg-type]

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        with pytest.raises(ToolError) as caught:
            _call("sota_summit_info")(summit_code="W7A/MN-001")
        message = str(caught.value)
        assert "HTTP 500" in message
        assert "no summit" not in message, "a server error was reported as an absence"

    def test_a_404_does_say_there_is_no_such_summit(self, monkeypatch) -> None:
        """SOTA-C12: the case the old catch existed for, still answered.

        A fix that made every failure say "the request failed" would be exactly
        as wrong in the other direction.
        """
        import urllib.error
        import urllib.request

        self._client(monkeypatch)

        def missing(*_a, **_k):
            raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)  # type: ignore[arg-type]

        monkeypatch.setattr(urllib.request, "urlopen", missing)
        with pytest.raises(ToolError, match="no record"):
            _call("sota_summit_info")(summit_code="XX/ZZ-999")

    def test_an_empty_body_also_says_there_is_no_such_summit(self, monkeypatch) -> None:
        """SOTA-C13: SOTA answers 200 with nothing for some unknown codes."""
        client = self._client(monkeypatch)
        monkeypatch.setattr(client, "_get_json", lambda url: None)
        with pytest.raises(ToolError, match="no summit XX/ZZ-999"):
            _call("sota_summit_info")(summit_code="XX/ZZ-999")


class TestToolErrorsAreFlagged:
    """A tool execution error belongs in the result with ``isError: true``."""

    @pytest.fixture
    def broken(self, monkeypatch):
        class Broken:
            def __getattr__(self, _name):
                def fail(*_args, **_kwargs):
                    raise RuntimeError("SOTA API request failed")
                return fail

        monkeypatch.setattr(server, "_get_client", lambda: Broken())

    UPSTREAM_CASES = [
        ("sota_spots", {}),
        ("sota_alerts", {}),
        ("sota_summit_info", {"summit_code": "W7A/MN-001"}),
        ("sota_summits_near", {"latitude": 43.6, "longitude": -116.0}),
    ]

    def test_the_cases_cover_every_tool_that_reaches_sota(self) -> None:
        """SOTA-C19: the parametrisation below cannot silently miss one."""
        assert {name for name, _ in self.UPSTREAM_CASES} == READS_SOTA

    @pytest.mark.parametrize("name,kwargs", UPSTREAM_CASES)
    def test_an_upstream_failure_is_flagged(self, broken, name, kwargs) -> None:
        """SOTA-C20: every tool that can fail, not a sample of them."""
        with pytest.raises(ToolError, match="SOTA API request failed"):
            _call(name)(**kwargs)


class TestAnEmptyAnswerIsNotAnError:
    """The distinction the specification draws."""

    def test_no_spots_is_a_successful_call(self, monkeypatch) -> None:
        """SOTA-C30: nobody on a summit right now is an answer."""
        class Quiet:
            def spots(self, **_kwargs):
                return []

        monkeypatch.setattr(server, "_get_client", lambda: Quiet())
        answer = _call("sota_spots")()
        assert isinstance(answer, dict)
        assert answer["total"] == 0

    def test_a_normal_lookup_is_a_successful_call(self) -> None:
        """SOTA-C31: the control, from mock mode."""
        answer = _call("sota_summit_info")(summit_code="W7A/MN-001")
        assert "summitCode" in answer or "summitName" in answer


class TestVersionInfoShape:
    def test_it_matches_the_shape_the_fleet_returns(self) -> None:
        """SOTA-C40: the convention that drifted because nobody asserted it."""
        info = _call("get_version_info")()
        assert info["service_name"] == "sota-mcp"
        assert info["service_version"]
        assert info["spec_version"]


class TestRegistration:
    def test_the_five_tools_a_client_sees(self) -> None:
        """SOTA-C50: calling a function directly is not proof a client can."""
        assert set(_tools()) == READS_SOTA | ANSWERS_FROM_THE_PACKAGE
