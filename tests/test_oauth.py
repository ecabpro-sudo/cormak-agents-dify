import base64
import hashlib
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx

from cormak import CormakError, RESOURCE
from cormak_oauth import CormakOAuth

CONFIG = {"client_id": "72786ba8-28ee-40dc-b36f-890e1d3f8f8b", "pkce_secret": "ab" * 32}
CALLBACK = "https://dify.example.com/console/api/oauth/plugin/cormak/callback"
ACCESS = "cmcp_a_" + "a" * 43
REFRESH = "cmcp_r_" + "r" * 43
CODE = "cmcp_c_" + "c" * 43


class OAuthTests(unittest.TestCase):
    def test_pkce_roundtrip_and_rotating_refresh(self):
        requests = []

        def handler(request):
            self.assertEqual(str(request.url), f"{RESOURCE}/token")
            body = parse_qs(request.content.decode())
            requests.append(body)
            if body["grant_type"] == ["authorization_code"]:
                verifier = body["code_verifier"][0]
                challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
                self.assertEqual(challenge, args["code_challenge"][0])
                self.assertEqual(body["redirect_uri"], [CALLBACK])
            else:
                self.assertEqual(body["refresh_token"], [REFRESH])
            return httpx.Response(200, json={"access_token": ACCESS, "refresh_token": REFRESH,
                                             "token_type": "Bearer", "expires_in": 3600})

        oauth = CormakOAuth(CONFIG, transport=httpx.MockTransport(handler))
        with patch("cormak_oauth.time.time", return_value=1800000000):
            args = parse_qs(urlsplit(oauth.authorization_url(CALLBACK)).query)
            credentials, expiry = oauth.exchange(CALLBACK, {"state": args["state"][0], "code": CODE})
            self.assertEqual(expiry, 1800003600)
            self.assertEqual(credentials, {"access_token": ACCESS, "refresh_token": REFRESH, "client_id": CONFIG["client_id"]})
            self.assertNotIn("pkce_secret", credentials)
            self.assertEqual(oauth.refresh(credentials)[0], credentials)
        self.assertEqual(len(requests), 2)

    def test_state_tampering_expiry_callback_and_workspace_are_rejected_before_network(self):
        def unexpected(_):
            self.fail("Untrusted callback must never reach the token endpoint")
        oauth = CormakOAuth(CONFIG, transport=httpx.MockTransport(unexpected))
        with patch("cormak_oauth.time.time", return_value=1800000000):
            state = parse_qs(urlsplit(oauth.authorization_url(CALLBACK)).query)["state"][0]
            for redirect, config, modified in (
                (CALLBACK + "/other", CONFIG, state),
                (CALLBACK, {**CONFIG, "pkce_secret": "cd" * 32}, state),
                (CALLBACK, CONFIG, state + "x"),
            ):
                with self.subTest(redirect=redirect, tampered=modified != state), self.assertRaises(CormakError):
                    CormakOAuth(config, transport=httpx.MockTransport(unexpected)).exchange(redirect, {"state": modified, "code": CODE})
        with patch("cormak_oauth.time.time", return_value=1800000301), self.assertRaisesRegex(CormakError, "invalid_oauth_state"):
            oauth.exchange(CALLBACK, {"state": state, "code": CODE})

    def test_refresh_timeout_does_not_retry_or_expose_tokens(self):
        calls = []
        def timeout(request):
            calls.append(request)
            raise httpx.ReadTimeout(f"raw private {REFRESH}")
        oauth = CormakOAuth(CONFIG, transport=httpx.MockTransport(timeout))
        with self.assertRaises(CormakError) as result:
            oauth.refresh({"refresh_token": REFRESH, "client_id": CONFIG["client_id"]})
        self.assertEqual(result.exception.code, "oauth_timeout_reconnect")
        self.assertNotIn(REFRESH, str(result.exception))
        self.assertEqual(len(calls), 1)

    def test_redirects_and_malformed_token_response_are_rejected(self):
        for response in (httpx.Response(302, headers={"Location": "https://attacker.example"}),
                         httpx.Response(200, json={"access_token": ACCESS, "refresh_token": REFRESH, "expires_in": 999999}),
                         httpx.Response(200, text=json.dumps([ACCESS, REFRESH]))):
            with self.subTest(response=response.status_code), self.assertRaises(CormakError):
                CormakOAuth(CONFIG, transport=httpx.MockTransport(lambda _: response)).refresh(
                    {"refresh_token": REFRESH, "client_id": CONFIG["client_id"]})


if __name__ == "__main__":
    unittest.main()
