#!/usr/bin/env python3
"""Authorize Dify through Cormak OAuth using an ephemeral loopback callback."""

import argparse
import base64
import hashlib
import hmac
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

ORIGIN = "https://mcp.cormak.app"
RESOURCE = f"{ORIGIN}/mcp"
SCOPES = "account:read employees:read employees:use photo:use store:use blog:use"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def post(path, body, *, form=False):
    headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    data = urllib.parse.urlencode(body) if form else json.dumps(body)
    req = urllib.request.Request(f"{ORIGIN}{path}", data=data.encode(), headers=headers, method="POST")
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=15) as response:
        return json.loads(response.read(32_769))


def authorize(manual):
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            args = urllib.parse.parse_qs(url.query)
            reported = args.get("state", [""])[0]
            code = args.get("code", [""])[0]
            valid = url.path == "/callback" and hmac.compare_digest(reported, state)
            if valid:
                result["code"] = code
            self.send_response(200 if valid else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(b"Return to your terminal." if valid else b"Invalid OAuth callback.")

        def log_message(self, *_args):
            pass

    with HTTPServer(("127.0.0.1", 0), Callback) as server:
        redirect = f"http://127.0.0.1:{server.server_port}/callback"
        client = post("/mcp/register", {
            "client_name": "Cormak Agents for Dify", "redirect_uris": [redirect],
            "token_endpoint_auth_method": "none",
        })["client_id"]
        query = urllib.parse.urlencode({
            "response_type": "code", "client_id": client, "redirect_uri": redirect, "scope": SCOPES,
            "resource": RESOURCE, "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        })
        link = f"{RESOURCE}/authorize?{query}"
        if manual or not webbrowser.open(link):
            print(f"Open in a browser on this computer:\n{link}", file=sys.stderr)
        print("Approve the requested scopes in Cormak. Waiting up to five minutes.", file=sys.stderr)
        server.timeout = 1
        deadline = time.monotonic() + 300
        while "code" not in result and time.monotonic() < deadline:
            server.handle_request()
    if not result.get("code"):
        raise ValueError("Authorization expired or was declined.")
    return post("/mcp/token", {
        "grant_type": "authorization_code", "client_id": client, "redirect_uri": redirect,
        "code": result["code"], "code_verifier": verifier, "resource": RESOURCE,
    }, form=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual", action="store_true", help="Print the authorization URL instead of opening it.")
    args = parser.parse_args()
    if not sys.stdout.isatty():
        parser.error("Run this in a private terminal so the access token is not written to a log or file.")
    try:
        token = authorize(args.manual)
    except urllib.error.HTTPError as error:
        parser.exit(1, f"Cormak OAuth rejected the request (HTTP {error.code}).\n")
    except (ValueError, OSError, KeyError):
        parser.exit(1, "Cormak authorization failed. Restart the connection setup.\n")
    print("Paste the access token into Dify’s Cormak OAuth access token secret field.\n"
          "Treat it as a password and close this terminal after copying.", file=sys.stderr)
    print(token["access_token"])


if __name__ == "__main__":
    main()
