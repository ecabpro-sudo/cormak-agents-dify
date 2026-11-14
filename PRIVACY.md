# Privacy

The plugin sends a Cormak OAuth access token in the Authorization header to
`https://mcp.cormak.app`. It exchanges authorization codes and rotating refresh
tokens only at that origin's `/mcp/token` endpoint. Dify stores access and refresh
tokens as provider credentials. A workspace administrator configures a public
client ID and a locally generated PKCE secret in Dify's OAuth client settings.
The secret stays in Dify and the plugin runtime; it is not sent to Cormak.
The setup helper sends the public client name and exact Dify callback URL to
Cormak's `/mcp/register` endpoint. No account password is collected by the plugin.
The plugin adds no separate credential storage, telemetry or analytics.

Tool inputs sent to Cormak include request IDs, agent and job IDs, task briefs,
media prompts, product facts and SEO topics and keywords. Cormak processes
generation inputs with its AI providers and maintains the account, approval,
operation and credit records needed for the feature. The results are sent
back to the invoking Dify workflow, where Dify may retain tool inputs and
outputs in run history. Private media links should only be shared with their
intended recipients.

Use non-sensitive material for workflows. Avoid customer identifiers, payment
or medical data, credentials and other confidential information in prompts
and briefs. You can remove the credential in Dify and revoke the connection
in [Cormak](https://app.cormak.app/mcp).

[Cormak privacy policy](https://cormak.app/privacy) · [Cormak terms](https://cormak.app/terms)
