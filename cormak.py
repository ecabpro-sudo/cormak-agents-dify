"""Fixed-origin client for the existing Cormak APIs."""

import json
import re
from uuid import UUID, uuid4

import httpx

ORIGIN = "https://mcp.cormak.app"
RESOURCE = f"{ORIGIN}/mcp"
SCOPES = "account:read employees:read employees:use photo:use store:use blog:use"
ACCESS_TOKEN = re.compile(r"cmcp_a_[A-Za-z0-9_-]{43}")
ERROR_CODE = re.compile(r"[a-z][a-z0-9_]{0,79}")
MAX_RESPONSE = 2 * 1024 * 1024

ERROR_MESSAGES = {
    "invalid_token": "Reconnect your Cormak account in Dify.",
    "access_revoked": "This Cormak connection has been revoked.",
    "permission_denied": "Grant the required scope in Cormak and reconnect.",
    "ai_consent_required": "Accept the AI terms in your Cormak settings.",
    "generation_limit_reached": "The Cormak connection generation limit was reached.",
    "limit_reached": "Check your Cormak balance and plan limits.",
    "idempotency_conflict": "That request ID is already bound to different inputs.",
    "quote_changed": "Check the current Cormak quote and confirm the new amount.",
    "rate_limit_reached": "Wait before polling again. Keep the original request ID.",
    "request_timeout": "Check status or retry the identical request with the same ID.",
    "oauth_timeout_reconnect": "Reconnect Cormak. Do not retry a rotating refresh token after a timeout.",
    "oauth_exchange_failed": "Reconnect Cormak and check your OAuth client settings.",
    "invalid_oauth_setup": "Check the Cormak OAuth client ID and workspace PKCE secret.",
}


class CormakError(Exception):
    def __init__(self, code, status=None):
        self.code = code
        self.status = status
        super().__init__(f"{code}: {ERROR_MESSAGES.get(code, 'Check the Cormak connection or operation status.')}")


def record(value):
    if not isinstance(value, dict):
        raise CormakError("invalid_response")
    return value


def error_code(value, fallback):
    return value if isinstance(value, str) and ERROR_CODE.fullmatch(value) else fallback


class CormakClient:
    def __init__(self, token, transport=None):
        if not isinstance(token, str) or not ACCESS_TOKEN.fullmatch(token.strip()):
            raise CormakError("invalid_token")
        self.http = httpx.Client(
            base_url=ORIGIN, headers={"Authorization": f"Bearer {token.strip()}"},
            follow_redirects=False, trust_env=False, transport=transport,
            timeout=httpx.Timeout(85, connect=8, write=10, pool=5),
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.http.close()

    def _post(self, path, body, protocol=None):
        headers = {"Accept": "application/json, text/event-stream"}
        if protocol:
            headers["MCP-Protocol-Version"] = protocol
        try:
            with self.http.stream("POST", path, json=body, headers=headers) as response:
                if response.is_redirect:
                    raise CormakError("unexpected_redirect", response.status_code)
                if response.status_code == 202 and "id" not in body and path == "/mcp":
                    return {}
                content = bytearray()
                for chunk in response.iter_bytes():
                    if len(content) + len(chunk) > MAX_RESPONSE:
                        raise CormakError("response_too_large")
                    content.extend(chunk)
                status = response.status_code
                event_stream = response.headers.get("content-type", "").startswith("text/event-stream")
        except httpx.TimeoutException:
            raise CormakError("request_timeout") from None
        except httpx.HTTPError:
            raise CormakError("connection_failed") from None
        fallback = {401: "invalid_token", 403: "permission_denied", 429: "rate_limit_reached"}.get(status, f"http_{status}")
        if status >= 400:
            try:
                code = error_code(record(json.loads(content)).get("error"), fallback)
            except (ValueError, CormakError):
                code = fallback
            raise CormakError(code, status)
        try:
            if event_stream:
                for event in content.decode().replace("\r\n", "\n").split("\n\n"):
                    data = "\n".join(line[5:].lstrip() for line in event.splitlines() if line.startswith("data:"))
                    if data and data != "[DONE]":
                        payload = record(json.loads(data))
                        if "id" in payload and payload["id"] == body.get("id"):
                            return payload
                raise CormakError("missing_rpc_response")
            return record(json.loads(content))
        except ValueError:
            raise CormakError("invalid_response") from None

    def _rpc(self, method, params, protocol=None):
        call_id = str(uuid4())
        value = self._post("/mcp", {"jsonrpc": "2.0", "id": call_id, "method": method, "params": params}, protocol)
        if value.get("jsonrpc") != "2.0" or value.get("id") != call_id:
            raise CormakError("invalid_response")
        if value.get("error"):
            raise CormakError("rpc_error")
        return record(value.get("result"))

    def mcp(self, name, **arguments):
        handshake = self._rpc("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "Cormak Agents for Dify", "version": "0.1.2"},
        })
        protocol = handshake.get("protocolVersion")
        if protocol not in {"2025-06-18", "2025-03-26", "2024-11-05", "2025-11-25"}:
            raise CormakError("unsupported_mcp_version")
        self._post("/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized"}, protocol)
        reply = self._rpc("tools/call", {"name": name, "arguments": arguments}, protocol)
        value = reply.get("structuredContent")
        if not isinstance(value, dict):
            try:
                value = record(json.loads(reply["content"][0]["text"]))
            except (ValueError, IndexError, KeyError, TypeError, CormakError):
                raise CormakError("tool_failed" if reply.get("isError") else "invalid_response") from None
        if name in {"get_generation", "get_video_status", "get_operation", "generate_image", "generate_video", "run_employee_task"}:
            # A terminal receipt is useful workflow data, including refund state.
            # Do not discard it merely because MCP also marks the tool as failed.
            terminal = value.get("status") in {"failed", "unknown", "denied", "expired"}
            refunded_failure = isinstance(value.get("refunded"), bool) and value.get("retryable") is False
            if terminal or refunded_failure:
                if "status" not in value:
                    value["status"] = "failed"
                return value
        if reply.get("isError") or value.get("error"):
            raise CormakError(error_code(value.get("error"), "tool_failed"))
        return value

    def store(self, action, **params):
        return self._action("/store", action, params)

    def blog(self, action, **params):
        return self._action("/blog", action, params)

    def _action(self, path, action, params):
        value = self._post(path, {"action": action, **params})
        if isinstance(value.get("error"), str):
            raise CormakError(error_code(value["error"], "service_error"))
        return value


def identifier(value):
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise CormakError("invalid_request_id") from None
    if not isinstance(value, str) or str(parsed) != value.lower() or parsed.version not in range(1, 9):
        raise CormakError("invalid_request_id")
    return str(parsed)
