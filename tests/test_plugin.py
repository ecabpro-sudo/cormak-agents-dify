import json
import unittest
import sys
from pathlib import Path

import httpx

from cormak import CormakClient, CormakError
from operations import media_status, product_copy, seo_status, start_agent, start_seo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experimental.video import start_video, video_status

REQUEST = "07d67532-cc92-4ae9-99e9-8136b4cbdbc3"
AGENT = "653b1dce-eea4-4c4e-9401-7dc6de01aefd"
TOKEN = "cmcp_a_" + "x" * 43


class ClientTests(unittest.TestCase):
    def client(self, handler):
        return CormakClient(TOKEN, transport=httpx.MockTransport(handler))

    def test_stateless_mcp_sse_handshake_and_result(self):
        calls = []

        def handler(request):
            body = json.loads(request.content)
            calls.append(body["method"])
            self.assertEqual(request.url.host, "mcp.cormak.app")
            self.assertEqual(request.headers["Authorization"], f"Bearer {TOKEN}")
            if body["method"] == "notifications/initialized":
                return httpx.Response(202, content=b"")
            if body["method"] == "initialize":
                result = {"protocolVersion": "2025-06-18"}
            else:
                self.assertEqual(request.headers["MCP-Protocol-Version"], "2025-06-18")
                self.assertEqual(body["params"]["name"], "get_account")
                result = {"structuredContent": {"available_ai_credits": 10}}
            event = {"jsonrpc": "2.0", "id": body["id"], "result": result}
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  text=f"event: message\r\ndata: {json.dumps(event)}\r\n\r\n")

        with self.client(handler) as client:
            self.assertEqual(client.mcp("get_account"), {"available_ai_credits": 10})
        self.assertEqual(calls, ["initialize", "notifications/initialized", "tools/call"])

    def test_redirect_is_not_followed(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(307, headers={"Location": "https://example.com"})
        with self.client(handler) as client, self.assertRaisesRegex(CormakError, "unexpected_redirect"):
            client.store("account")
        self.assertEqual(calls, ["https://mcp.cormak.app/store"])

    def test_terminal_video_receipt_preserves_failure_and_refund(self):
        def handler(request):
            body = json.loads(request.content)
            if body["method"] == "notifications/initialized":
                return httpx.Response(202)
            result = {"protocolVersion": "2025-06-18"} if body["method"] == "initialize" else {
                "isError": True, "structuredContent": {"status": "failed", "tool": "generate_video",
                    "request_id": REQUEST, "result": {"error": "video_failed", "refunded": True, "retryable": False}},
            }
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})
        with self.client(handler) as client:
            value = client.mcp("get_generation", request_id=REQUEST)
        self.assertEqual(value["status"], "failed")
        self.assertTrue(value["result"]["refunded"])

    def test_timeout_has_no_retry_or_request_details(self):
        calls = []

        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout(f"raw request accidentally contains {TOKEN}")
        with self.client(handler) as client, self.assertRaises(CormakError) as error:
            client.store("fill_text", request_id=REQUEST)
        self.assertEqual(error.exception.code, "request_timeout")
        self.assertNotIn(TOKEN, str(error.exception))
        self.assertEqual(len(calls), 1)

    def test_http_errors_are_bounded_and_signed_urls_are_not_fetched(self):
        with self.client(lambda _: httpx.Response(429, json={"error": f"unexpected {TOKEN}"})) as client:
            with self.assertRaisesRegex(CormakError, "rate_limit_reached"):
                client.blog("quote")
        url = "https://storage.example.com/private"
        with self.client(lambda _: httpx.Response(200, json={"image": {"url": url}})) as client:
            self.assertEqual(client.blog("article")["image"]["url"], url)


class Service:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def mcp(self, name, **params):
        return self.call("mcp", name, params)

    def store(self, name, **params):
        return self.call("store", name, params)

    def blog(self, name, **params):
        return self.call("blog", name, params)

    def call(self, surface, name, params):
        self.calls.append((surface, name, params))
        return next(self.replies)


class OperationTests(unittest.TestCase):
    def test_paid_gate_blocks_before_network(self):
        for operation in (start_agent, start_video, product_copy, start_seo):
            client = Service([])
            with self.assertRaisesRegex(CormakError, "paid_run_disabled"):
                operation(client, {"request_id": REQUEST, "allow_paid_run": "true"})
            self.assertEqual(client.calls, [])

    def test_draft_approval_is_returned_and_retry_reuses_id(self):
        agent = {"id": AGENT, "name": "Copy", "role": "copywriter", "archived": False}
        awaiting = {"status": "awaiting_confirmation", "approval_url": "https://app.cormak.app/mcp?approval_id=1"}
        client = Service([{"items": [agent]}, awaiting, {"items": [agent]}, {"status": "running"}])
        args = {"agent_id": AGENT, "kind": "text", "brief": "Draft a product headline", "request_id": REQUEST, "allow_paid_run": True}
        self.assertEqual(start_agent(client, args), awaiting)
        self.assertEqual(start_agent(client, args), {"status": "running"})
        self.assertEqual(client.calls[1], client.calls[3])
        self.assertEqual(client.calls[1][2]["request_id"], REQUEST)

    def test_video_status_uses_backend_id_only_after_dispatch(self):
        running = {"tool": "generate_video", "status": "running", "backend_request_id": AGENT}
        client = Service([running, {**running, "status": "complete"}, {"status": "succeeded"}])
        self.assertEqual(video_status(client, {"request_id": REQUEST}), running)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(video_status(client, {"request_id": REQUEST})["video"]["status"], "succeeded")
        self.assertEqual(client.calls[-1], ("mcp", "get_video_status", {"request_id": AGENT}))

    def test_seo_quote_cap_and_completed_article_fetch(self):
        client = Service([{"job": {"id": AGENT}}, {"articles": [{"id": REQUEST, "status": "complete"}]},
                          {"article": {"content": {"title": "Example"}}}])
        start_seo(client, {"request_id": REQUEST, "topic": "Reusable packaging",
                           "expected_credits": 2.0, "allow_paid_run": True})
        self.assertEqual(client.calls[0][2]["expected_credits"], 2)
        self.assertEqual(client.calls[0][2]["brief"]["with_images"], False)
        self.assertEqual(seo_status(client, {"job_id": AGENT})["completed_article"]["content"]["title"], "Example")


if __name__ == "__main__":
    unittest.main()
