from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from dify_plugin.errors.tool import ToolProviderOAuthError
from dify_plugin.entities.oauth import ToolOAuthCredentials

from cormak import CormakClient, CormakError
from cormak_oauth import CormakOAuth


class CormakAgentsProvider(ToolProvider):
    def _validate_credentials(self, credentials):
        try:
            with CormakClient(credentials.get("access_token")) as client:
                client.mcp("get_account")
        except CormakError as error:
            raise ToolProviderCredentialValidationError(str(error)) from None

    def _oauth_get_authorization_url(self, redirect_uri, system_credentials):
        try:
            return CormakOAuth(system_credentials).authorization_url(redirect_uri)
        except CormakError as error:
            raise ToolProviderOAuthError(str(error)) from None

    def _oauth_get_credentials(self, redirect_uri, system_credentials, request):
        try:
            credentials, expiry = CormakOAuth(system_credentials).exchange(redirect_uri, request.args)
            return ToolOAuthCredentials(credentials=credentials, expires_at=expiry)
        except CormakError as error:
            raise ToolProviderOAuthError(str(error)) from None

    def _oauth_refresh_credentials(self, redirect_uri, system_credentials, credentials):
        try:
            updated, expiry = CormakOAuth(system_credentials).refresh(credentials)
            return ToolOAuthCredentials(credentials=updated, expires_at=expiry)
        except CormakError as error:
            raise ToolProviderOAuthError(str(error)) from None
