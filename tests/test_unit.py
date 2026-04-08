"""
Offline unit tests — no network required.

Tests cover:
  - JWT token expiry detection (_is_token_expired)
  - HTTP client behaviour (mocked via respx): success, 401, 429
  - Tool-level error handling: auth/rate-limit errors return structured dicts
  - faostat_get_data truncation logic
"""

import base64
import json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

import faostat_mcp.client as client_module
from faostat_mcp.client import (
    FAOSTATAuthError,
    FAOSTATRateLimitError,
    TokenManager,
    _is_token_expired,
    faostat_get,
)
from faostat_mcp.server import (
    _format_rows,
    faostat_get_codes,
    faostat_get_data,
    faostat_get_rankings,
    faostat_list_groups,
    faostat_ping,
)

# ---------------------------------------------------------------------------
# Helpers — crafted JWTs (signature is never verified by _is_token_expired)
# ---------------------------------------------------------------------------

def _make_jwt(exp: int) -> str:
    """Return a minimal JWT string with the given exp claim."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload_bytes = json.dumps({"exp": exp, "sub": "test"}).encode()
    payload = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


# Non-expiring token valid until year 2286
_VALID_TOKEN = _make_jwt(9_999_999_999)
# Token that expired one hour ago
_EXPIRED_TOKEN = _make_jwt(int(time.time()) - 3600)
# Token that expires in 30 seconds (within the 60s buffer)
_NEAR_EXPIRY_TOKEN = _make_jwt(int(time.time()) + 30)


# ---------------------------------------------------------------------------
# Autouse fixture — resets module-level singletons between every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singletons(monkeypatch):
    """Prevent state leaking between tests via module-level globals."""
    monkeypatch.setattr(client_module, "_token_manager", None)
    monkeypatch.setattr(client_module, "_last_request_time", 0.0)
    monkeypatch.setenv("FAOSTAT_API_TOKEN", _VALID_TOKEN)
    monkeypatch.delenv("FAOSTAT_USERNAME", raising=False)
    monkeypatch.delenv("FAOSTAT_PASSWORD", raising=False)
    yield
    monkeypatch.setattr(client_module, "_token_manager", None)
    monkeypatch.setattr(client_module, "_last_request_time", 0.0)


# ---------------------------------------------------------------------------
# Token expiry detection — pure unit tests, no mocking needed
# ---------------------------------------------------------------------------

def test_token_not_expired_for_far_future_exp():
    assert _is_token_expired(_VALID_TOKEN) is False


def test_token_expired_for_past_exp():
    assert _is_token_expired(_EXPIRED_TOKEN) is True


def test_token_expired_within_60s_buffer():
    """Token expiring in 30 seconds is treated as expired (60s buffer)."""
    assert _is_token_expired(_NEAR_EXPIRY_TOKEN) is True


def test_token_malformed_does_not_raise():
    """Malformed JWT must return False, not raise."""
    assert _is_token_expired("not.a.jwt") is False
    assert _is_token_expired("") is False
    assert _is_token_expired("only_one_part") is False


# ---------------------------------------------------------------------------
# Client behaviour — mocked via respx
# ---------------------------------------------------------------------------

@respx.mock
async def test_faostat_get_returns_parsed_json():
    """Successful 200 response is parsed and returned as a dict/list."""
    respx.get("https://faostatservices.fao.org/api/v1/ping").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    result = await faostat_get("/ping")
    assert result == {"status": "ok"}


@respx.mock
async def test_faostat_get_raises_auth_error_on_401_no_credentials():
    """401 with no credentials → FAOSTATAuthError (no infinite retry)."""
    respx.get("https://faostatservices.fao.org/api/v1/ping").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    with pytest.raises(FAOSTATAuthError):
        await faostat_get("/ping")


@respx.mock
async def test_faostat_get_raises_rate_limit_error_on_429():
    """429 response → FAOSTATRateLimitError."""
    respx.get("https://faostatservices.fao.org/api/v1/ping").mock(
        return_value=httpx.Response(429, text="Too Many Requests")
    )
    with pytest.raises(FAOSTATRateLimitError):
        await faostat_get("/ping")


@respx.mock
async def test_faostat_get_returns_status_dict_for_empty_body():
    """Empty response body returns {"status": <code>} instead of crashing."""
    respx.get("https://faostatservices.fao.org/api/v1/ping").mock(
        return_value=httpx.Response(200, content=b"")
    )
    result = await faostat_get("/ping")
    assert result == {"status": 200}


# ---------------------------------------------------------------------------
# Tool-level error handling — mock faostat_get/faostat_post at server level
# ---------------------------------------------------------------------------

async def test_tool_returns_error_dict_on_auth_error():
    """Tools catch FAOSTATAuthError and return a structured error dict."""
    with patch("faostat_mcp.server.faostat_get", side_effect=FAOSTATAuthError("Token expired")):
        result = json.loads(await faostat_ping())
    assert result["error"] == "FAOSTATAuthError"
    assert "Token expired" in result["message"]


async def test_tool_returns_error_dict_on_rate_limit():
    """Tools catch FAOSTATRateLimitError and return a structured error dict."""
    with patch("faostat_mcp.server.faostat_get", side_effect=FAOSTATRateLimitError("429")):
        result = json.loads(await faostat_list_groups())
    assert result["error"] == "FAOSTATRateLimitError"


# ---------------------------------------------------------------------------
# faostat_get_data — truncation logic
# ---------------------------------------------------------------------------

async def test_faostat_get_data_truncates_list_response():
    """List responses larger than limit are truncated with metadata."""
    big_list = [{"row": i} for i in range(600)]
    with patch("faostat_mcp.server.faostat_get", return_value=big_list):
        result = json.loads(await faostat_get_data(domain_code="QCL", limit=500))
    assert result["_truncated"] is True
    assert result["_total_rows"] == 600
    assert result["_returned_rows"] == 500
    assert len(result["data"]) == 500


async def test_faostat_get_data_truncates_dict_with_data_key():
    """Dict responses with a 'data' list key are also truncated correctly."""
    big_response = {"data": [{"row": i} for i in range(600)], "metadata": {}}
    with patch("faostat_mcp.server.faostat_get", return_value=big_response):
        result = json.loads(await faostat_get_data(domain_code="QCL", limit=500))
    assert result["_truncated"] is True
    assert result["_returned_rows"] == 500


async def test_faostat_get_data_no_truncation_when_under_limit():
    """Responses under the limit are returned unchanged (no _truncated key)."""
    small_list = [{"row": i} for i in range(10)]
    with patch("faostat_mcp.server.faostat_get", return_value=small_list):
        result = json.loads(await faostat_get_data(domain_code="QCL", limit=500))
    assert isinstance(result, list)
    assert result == small_list


async def test_faostat_get_data_limit_zero_disables_truncation():
    """Setting limit=0 disables truncation entirely."""
    big_list = [{"row": i} for i in range(1000)]
    with patch("faostat_mcp.server.faostat_get", return_value=big_list):
        result = json.loads(await faostat_get_data(domain_code="QCL", limit=0))
    assert isinstance(result, list)
    assert len(result) == 1000


# ---------------------------------------------------------------------------
# /auth/login endpoint — token refresh via the FAOSTAT backend
# ---------------------------------------------------------------------------

_BASE_URL = "https://faostatservices.fao.org/api/v1"
_AUTH_URL = f"{_BASE_URL}/auth/login"


def _make_auth_response(token: str) -> dict:
    """Build the AuthenticationResult payload returned by /auth/login."""
    return {
        "AuthenticationResult": {
            "AccessToken": token,
            "ExpiresIn": 3600,
            "IdToken": "id-token-value",
            "RefreshToken": "refresh-token-value",
            "TokenType": "Bearer",
        },
        "ChallengeParameters": {},
    }


@respx.mock
async def test_login_via_auth_endpoint_succeeds():
    """_login() POSTs form-encoded credentials to /auth/login and returns AccessToken."""
    fresh_token = _make_jwt(int(time.time()) + 3600)
    respx.post(_AUTH_URL).mock(
        return_value=httpx.Response(200, json=_make_auth_response(fresh_token))
    )
    tm = TokenManager(base_url=_BASE_URL, username="user@example.com", password="secret")
    token = await tm._login()
    assert token == fresh_token


@respx.mock
async def test_login_via_auth_endpoint_sends_form_encoded_body():
    """_login() must use application/x-www-form-urlencoded (not JSON)."""
    fresh_token = _make_jwt(int(time.time()) + 3600)
    captured = {}

    def capture(request):
        captured["content_type"] = request.headers.get("content-type", "")
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=_make_auth_response(fresh_token))

    respx.post(_AUTH_URL).mock(side_effect=capture)
    tm = TokenManager(base_url=_BASE_URL, username="user@example.com", password="secret")
    await tm._login()

    assert "application/x-www-form-urlencoded" in captured["content_type"]
    assert "username=user%40example.com" in captured["body"] or "username=user@example.com" in captured["body"]
    assert "password=secret" in captured["body"]


@respx.mock
async def test_login_via_auth_endpoint_raises_auth_error_on_401():
    """_login() raises FAOSTATAuthError when /auth/login returns 401."""
    respx.post(_AUTH_URL).mock(return_value=httpx.Response(401))
    tm = TokenManager(base_url=_BASE_URL, username="wrong@example.com", password="bad")
    with pytest.raises(FAOSTATAuthError, match="invalid username or password"):
        await tm._login()


@respx.mock
async def test_login_via_auth_endpoint_raises_auth_error_on_400():
    """_login() raises FAOSTATAuthError when /auth/login returns 400 (bad request)."""
    respx.post(_AUTH_URL).mock(return_value=httpx.Response(400, json={"detail": "Bad Request"}))
    tm = TokenManager(base_url=_BASE_URL, username="user@example.com", password="wrong")
    with pytest.raises(FAOSTATAuthError, match="invalid username or password"):
        await tm._login()


@respx.mock
async def test_get_token_triggers_auth_endpoint_when_token_expired():
    """get_token() calls /auth/login when the stored token is expired."""
    fresh_token = _make_jwt(int(time.time()) + 3600)
    respx.post(_AUTH_URL).mock(
        return_value=httpx.Response(200, json=_make_auth_response(fresh_token))
    )
    tm = TokenManager(
        base_url=_BASE_URL,
        token=_EXPIRED_TOKEN,
        username="user@example.com",
        password="secret",
    )
    token = await tm.get_token()
    assert token == fresh_token


@respx.mock
async def test_force_refresh_uses_auth_endpoint():
    """force_refresh() fetches a new token from /auth/login and updates internal state."""
    fresh_token = _make_jwt(int(time.time()) + 3600)
    respx.post(_AUTH_URL).mock(
        return_value=httpx.Response(200, json=_make_auth_response(fresh_token))
    )
    tm = TokenManager(
        base_url=_BASE_URL,
        token=_EXPIRED_TOKEN,
        username="user@example.com",
        password="secret",
    )
    refreshed = await tm.force_refresh()
    assert refreshed == fresh_token
    assert tm._token == fresh_token


@respx.mock
async def test_faostat_get_auto_refreshes_via_auth_endpoint_on_401():
    """faostat_get() transparently refreshes via /auth/login when the API returns 401."""
    fresh_token = _make_jwt(int(time.time()) + 3600)

    # First API call → 401; second (after refresh) → 200
    api_route = respx.get("https://faostatservices.fao.org/api/v1/ping")
    api_route.side_effect = [
        httpx.Response(401, text="Unauthorized"),
        httpx.Response(200, json={"status": "ok"}),
    ]
    respx.post(_AUTH_URL).mock(
        return_value=httpx.Response(200, json=_make_auth_response(fresh_token))
    )

    # Seed the module-level manager with credentials so auto-refresh is enabled
    client_module._token_manager = TokenManager(
        base_url=_BASE_URL,
        token=_VALID_TOKEN,
        username="user@example.com",
        password="secret",
    )

    result = await faostat_get("/ping")
    assert result == {"status": "ok"}


# ---------------------------------------------------------------------------
# _format_rows helper — pure unit tests
# ---------------------------------------------------------------------------

_SAMPLE_ROWS = [
    {"Area": "India", "Item": "Wheat", "Year": 2024, "Value": "109590000"},
    {"Area": "USA", "Item": "Wheat", "Year": 2024, "Value": "49691000"},
    {"Area": "China", "Item": "Wheat", "Year": 2024, "Value": "136590000"},
]


def test_format_rows_objects():
    """'objects' format returns the original JSON array."""
    result = json.loads(_format_rows(_SAMPLE_ROWS, response_format="objects"))
    assert result == _SAMPLE_ROWS


def test_format_rows_compact():
    """'compact' format returns columns + rows arrays."""
    result = json.loads(_format_rows(_SAMPLE_ROWS, response_format="compact"))
    assert result["columns"] == ["Area", "Item", "Year", "Value"]
    assert len(result["rows"]) == 3
    assert result["rows"][0] == ["India", "Wheat", 2024, "109590000"]


def test_format_rows_csv():
    """'csv' format returns plain CSV text with header."""
    result = _format_rows(_SAMPLE_ROWS, response_format="csv")
    lines = result.strip().split("\n")
    assert lines[0] == "Area,Item,Year,Value"
    assert lines[1] == "India,Wheat,2024,109590000"
    assert len(lines) == 4  # header + 3 data rows


def test_format_rows_csv_with_commas_in_values():
    """CSV correctly quotes values containing commas."""
    rows = [{"Area": "China, mainland", "Value": "100"}]
    result = _format_rows(rows, response_format="csv")
    lines = result.strip().split("\n")
    assert '"China, mainland"' in lines[1]


def test_format_rows_field_selection():
    """fields parameter filters to specified columns."""
    result = json.loads(_format_rows(_SAMPLE_ROWS, fields=["Area", "Value"]))
    assert list(result[0].keys()) == ["Area", "Value"]
    assert len(result[0]) == 2


def test_format_rows_field_selection_with_compact():
    """fields + compact format returns filtered columns."""
    result = json.loads(_format_rows(
        _SAMPLE_ROWS, response_format="compact", fields=["Area", "Value"]
    ))
    assert result["columns"] == ["Area", "Value"]
    assert result["rows"][0] == ["India", "109590000"]


def test_format_rows_empty_list():
    """Empty input returns '[]' regardless of format."""
    assert _format_rows([], response_format="objects") == "[]"
    assert _format_rows([], response_format="compact") == "[]"
    assert _format_rows([], response_format="csv") == "[]"


def test_format_rows_invalid_fields_ignored():
    """Non-existent field names fall back to all columns."""
    result = json.loads(_format_rows(_SAMPLE_ROWS, fields=["NonExistent"]))
    # All original columns retained when no valid fields match
    assert list(result[0].keys()) == ["Area", "Item", "Year", "Value"]


# ---------------------------------------------------------------------------
# faostat_get_data — response format integration
# ---------------------------------------------------------------------------

async def test_faostat_get_data_default_limit_is_50():
    """Default limit is now 50 (not 500)."""
    big_list = [{"Area": "X", "Value": i} for i in range(100)]
    with patch("faostat_mcp.server.faostat_get", return_value=big_list):
        result = json.loads(await faostat_get_data(domain_code="QCL"))
    assert result["_truncated"] is True
    assert result["_returned_rows"] == 50


async def test_faostat_get_data_show_codes_default_false():
    """show_codes defaults to False — verify param passed to API."""
    with patch("faostat_mcp.server.faostat_get", return_value=[]) as mock_get:
        await faostat_get_data(domain_code="QCL")
    call_params = mock_get.call_args[1]["params"]
    assert call_params["show_codes"] is False
    assert call_params["show_flags"] is False


async def test_faostat_get_data_compact_format():
    """response_format='compact' returns columnar structure."""
    rows = [{"Area": "India", "Value": "100"}]
    with patch("faostat_mcp.server.faostat_get", return_value=rows):
        result = json.loads(await faostat_get_data(
            domain_code="QCL", response_format="compact"
        ))
    assert "columns" in result
    assert "rows" in result
    assert result["columns"] == ["Area", "Value"]


async def test_faostat_get_data_csv_format():
    """response_format='csv' returns plain CSV text."""
    rows = [{"Area": "India", "Value": "100"}]
    with patch("faostat_mcp.server.faostat_get", return_value=rows):
        result = await faostat_get_data(domain_code="QCL", response_format="csv")
    lines = result.strip().split("\n")
    assert lines[0] == "Area,Value"
    assert lines[1] == "India,100"


async def test_faostat_get_data_csv_truncated():
    """Truncated CSV includes metadata comment line."""
    big_list = [{"Area": "X", "Value": str(i)} for i in range(100)]
    with patch("faostat_mcp.server.faostat_get", return_value=big_list):
        result = await faostat_get_data(
            domain_code="QCL", response_format="csv", limit=10
        )
    assert result.startswith("# truncated:")
    lines = result.strip().split("\n")
    # Comment + header + 10 data rows
    assert len(lines) == 12


async def test_faostat_get_data_field_selection():
    """fields parameter filters columns in the response."""
    rows = [{"Area": "India", "Item": "Wheat", "Value": "100"}]
    with patch("faostat_mcp.server.faostat_get", return_value=rows):
        result = json.loads(await faostat_get_data(
            domain_code="QCL", fields="Area,Value"
        ))
    assert list(result[0].keys()) == ["Area", "Value"]


async def test_faostat_get_data_invalid_format_returns_error():
    """Invalid response_format returns an error dict."""
    result = json.loads(await faostat_get_data(
        domain_code="QCL", response_format="xml"
    ))
    assert result["error"] == "ValueError"


# ---------------------------------------------------------------------------
# faostat_get_codes — limit parameter
# ---------------------------------------------------------------------------

async def test_faostat_get_codes_truncates_when_limit_set():
    """faostat_get_codes truncates large code lists when limit > 0."""
    codes = [{"code": str(i), "description": f"Item {i}"} for i in range(300)]
    with patch("faostat_mcp.server.faostat_get", return_value=codes):
        result = json.loads(await faostat_get_codes(
            dimension_id="item", domain_code="QCL", limit=50
        ))
    assert result["_truncated"] is True
    assert result["_total_codes"] == 300
    assert len(result["data"]) == 50


async def test_faostat_get_codes_no_limit_returns_all():
    """faostat_get_codes with default limit=0 returns all codes."""
    codes = [{"code": str(i)} for i in range(300)]
    with patch("faostat_mcp.server.faostat_get", return_value=codes):
        result = json.loads(await faostat_get_codes(
            dimension_id="item", domain_code="QCL"
        ))
    assert len(result) == 300


# ---------------------------------------------------------------------------
# faostat_get_rankings — response_format parameter
# ---------------------------------------------------------------------------

async def test_faostat_get_rankings_compact_format():
    """faostat_get_rankings supports compact format."""
    rankings = [{"Area": "China", "Value": "136M", "Rank": 1}]
    with patch("faostat_mcp.server.faostat_post", return_value=rankings):
        result = json.loads(await faostat_get_rankings(
            domain_code="QCL", element_code="5510",
            item_code="15", year="2022", response_format="compact"
        ))
    assert "columns" in result
    assert "rows" in result
