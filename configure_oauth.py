#!/usr/bin/env python3
"""Register a Cormak public OAuth client for the exact callback shown by Dify."""

import argparse
import secrets
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent / "cormak_agents"))

from cormak import ORIGIN, CormakError, identifier
from cormak_oauth import callback_uri


def register(redirect):
    redirect = callback_uri(redirect)
    with httpx.Client(follow_redirects=False, trust_env=False, timeout=15) as client:
        response = client.post(f"{ORIGIN}/mcp/register", json={
            "client_name": "Cormak Agents for Dify", "redirect_uris": [redirect],
            "token_endpoint_auth_method": "none",
        })
    if response.status_code != 201 or len(response.content) > 32768:
        raise CormakError("oauth_registration_failed", response.status_code)
    return identifier(response.json().get("client_id"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redirect-uri", required=True, help="Exact OAuth callback shown by Dify.")
    args = parser.parse_args()
    if not sys.stdout.isatty():
        parser.error("Run in a private terminal so the setup secret is not written to logs or a file.")
    try:
        client_id = register(args.redirect_uri)
    except (CormakError, httpx.HTTPError, ValueError, AttributeError):
        parser.exit(1, "OAuth registration failed. Check the callback and try again.\n")
    print("Paste these into Dify's Cormak Agents OAuth client settings, then close this terminal.")
    print(f"client_id: {client_id}\npkce_secret: {secrets.token_hex(32)}")


if __name__ == "__main__":
    main()
