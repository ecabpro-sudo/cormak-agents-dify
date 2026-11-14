"""Public-client OAuth with PKCE, fixed destinations and bounded responses.

Dify owns the single-use, browser-bound OAuth callback context and serializes
credential refreshes. A workspace secret binds PKCE state to the configured
client and exact callback, without keeping per-flow state in a plugin process.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

import httpx

from cormak import ACCESS_TOKEN, ORIGIN, RESOURCE, SCOPES, CormakError, identifier

REFRESH_TOKEN = re.compile(r"cmcp_r_[A-Za-z0-9_-]{43}")
CODE = re.compile(r"cmcp_c_[A-Za-z0-9_-]{43}")


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def callback_uri(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise CormakError("invalid_oauth_callback")
    url = urlsplit(value)
    if (url.username or url.password or url.query or url.fragment or not url.hostname
            or (url.scheme != "https" and not (url.scheme == "http" and url.hostname in ("127.0.0.1", "localhost", "::1")))):
        raise CormakError("invalid_oauth_callback")
    return value


class CormakOAuth:
    def __init__(self, config, transport=None):
        self.client_id = identifier(config.get("client_id"))
        secret = config.get("pkce_secret")
        if not isinstance(secret, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", secret):
            raise CormakError("invalid_oauth_setup")
        self.key = bytes.fromhex(secret)
        self.transport = transport

    def _mac(self, purpose, value, redirect):
        payload = "\0".join((purpose, self.client_id, redirect, value)).encode()
        return b64(hmac.digest(self.key, payload, "sha256"))

    def authorization_url(self, redirect):
        redirect = callback_uri(redirect)
        payload = f"{int(time.time())}.{secrets.token_urlsafe(32)}"
        state = f"{payload}.{self._mac('state', payload, redirect)}"
        verifier = self._mac("verifier", state, redirect)
        return f"{RESOURCE}/authorize?" + urlencode({
            "response_type": "code", "client_id": self.client_id, "redirect_uri": redirect,
            "resource": RESOURCE, "scope": SCOPES, "state": state,
            "code_challenge": b64(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256",
        })

    def exchange(self, redirect, args):
        redirect = callback_uri(redirect)
        state, code = args.get("state"), args.get("code")
        if args.get("error"):
            raise CormakError("oauth_declined")
        if (not isinstance(state, str) or len(state) > 200
                or not re.fullmatch(r"[0-9]{10,12}\.[A-Za-z0-9_-]{43}\.[A-Za-z0-9_-]{43}", state)
                or not isinstance(code, str) or not CODE.fullmatch(code)):
            raise CormakError("invalid_oauth_callback")
        payload, signature = state.rsplit(".", 1)
        age = time.time() - int(payload.split(".", 1)[0])
        if not 0 <= age <= 300 or not hmac.compare_digest(signature, self._mac("state", payload, redirect)):
            raise CormakError("invalid_oauth_state")
        return self._token({"grant_type": "authorization_code", "code": code,
                            "redirect_uri": redirect, "code_verifier": self._mac("verifier", state, redirect)})

    def refresh(self, credentials):
        token = credentials.get("refresh_token")
        if (credentials.get("client_id") != self.client_id or not isinstance(token, str)
                or not REFRESH_TOKEN.fullmatch(token)):
            raise CormakError("invalid_oauth_setup")
        # Never retry a rotating refresh token: a lost response requires reconnect.
        return self._token({"grant_type": "refresh_token", "refresh_token": token})

    def _token(self, fields):
        try:
            with httpx.Client(follow_redirects=False, trust_env=False, transport=self.transport,
                              timeout=httpx.Timeout(15, connect=8)) as client:
                with client.stream("POST", f"{RESOURCE}/token", data={
                    **fields, "client_id": self.client_id, "resource": RESOURCE,
                }) as response:
                    if response.status_code != 200:
                        raise CormakError("oauth_exchange_failed", response.status_code)
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        if len(raw) + len(chunk) > 32768:
                            raise CormakError("invalid_oauth_response")
                        raw.extend(chunk)
            data = json.loads(raw)
        except httpx.TimeoutException:
            raise CormakError("oauth_timeout_reconnect") from None
        except httpx.HTTPError:
            raise CormakError("oauth_connection_failed") from None
        except ValueError:
            raise CormakError("invalid_oauth_response") from None
        if not isinstance(data, dict):
            raise CormakError("invalid_oauth_response")
        access, refresh, expiry = data.get("access_token"), data.get("refresh_token"), data.get("expires_in")
        if (not isinstance(access, str) or not ACCESS_TOKEN.fullmatch(access)
                or not isinstance(refresh, str) or not REFRESH_TOKEN.fullmatch(refresh)
                or type(expiry) is not int or not 60 <= expiry <= 3600
                or data.get("token_type", "").lower() != "bearer"):
            raise CormakError("invalid_oauth_response")
        return {"access_token": access, "refresh_token": refresh, "client_id": self.client_id}, int(time.time()) + expiry
