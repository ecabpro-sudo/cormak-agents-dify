# Cormak Agents for Dify

Use Cormak AI agents, image generation, product copy and SEO article
drafts in Dify workflows and chatflows. You need a Cormak account and a Dify
workspace with plugin installation enabled. Dify 1.19.0 or later is required.

[Source repository](https://github.com/ecabpro-sudo/cormak-agents-dify) ·
[MIT license](https://github.com/ecabpro-sudo/cormak-agents-dify/blob/main/LICENSE)

## Connect your account

1. Install the package under **Plugins → Install plugin → Local Package File** in a
   Dify test workspace that permits local packages. Use a trusted copy of the package.
2. Open the provider's **OAuth client settings** as a workspace administrator.
   Copy the exact callback URL displayed by Dify. In a private terminal, from
   the source repository's root directory with its `requirements.txt`
   installed, run:

   ```sh
   python configure_oauth.py --redirect-uri 'https://YOUR-DIFY-EXACT-CALLBACK'
   ```

   The helper registers a public OAuth client with Cormak and generates a
   workspace PKCE secret. Paste its `client_id` and `pkce_secret` into Dify's
   OAuth client settings. This is a one-time setup per Dify workspace. The
   secret is generated locally; it is not a Cormak account password.
3. Choose **Authorize** in the Cormak Agents provider. Sign in to Cormak and
   review the permissions and generation limit. Dify stores access and rotating
   refresh tokens as credentials and refreshes them automatically. The plugin
   never receives your Cormak password. Reconnect after revocation or expiry
   of the Cormak grant, or if a refresh response is lost.
4. Add a Cormak Agents tool node. Test **Get Credit Balance** first. Each tool
   returns a structured JSON result. Treat returned drafts and links as private.

Use `account:read` for connection validation. Add `employees:read employees:use`
for agent drafts, `photo:use` for images, `store:use` for
product copy and `blog:use` for SEO articles. Cormak supports revocation in
[Connections](https://app.cormak.app/mcp).

Each workspace must use its own client ID and PKCE secret. Keep the OAuth
credential private unless all workspace members should have the same Cormak
access. Dify 1.19.0 serializes concurrent refreshes for each credential; do
not share one refresh token between separate credentials or installations.

## Tools

| Tool | What it does |
| --- | --- |
| Get Credit Balance | Reads the plan and available AI and video credits. |
| List Cormak Agents | Lists supported active agents and their task kinds. |
| Run Cormak Agent / Get Agent Run Status | Creates and retrieves private drafts for supported copywriting, social, support FAQ, sales and marketplace tasks. |
| Generate Image | Requests a prompt-based image (two AI credits). |
| Get Image Status | Checks an image request and returns its temporary media URL where available. |
| Write Product Copy | Writes a title, descriptions and SEO metadata from supplied product facts. |
| Quote SEO Article / Generate SEO Article / Get SEO Article | Quotes, starts and retrieves one article draft. |

## Example workflow

Use **List Cormak Agents** to select a copywriting agent and its `text` task.
Supply a non-sensitive brief and a stable UUID from your workflow. Enable
**Allow credit use** in the node only if the workflow can spend Cormak credits.

When an agent or image tool returns `awaiting_confirmation`, open
`approval_url` as the Cormak account owner and review the request. Call the
same tool again with identical data and the same UUID after approval.
Use the status tool for subsequent checks. Keep retries bounded and stop at
terminal states. If an outcome is unknown, check the existing operation or
your Cormak library before taking any action.

For a product listing, supply verified product facts. Product copy spends
one AI credit when enabled. SEO uses the current quote from **Quote SEO
Article**. Set the quoted maximum in **Generate SEO Article** and use the
returned job ID in **Get SEO Article**. Product copy and SEO can start immediately
when enabled. Cormak enforces plan, consent, credit and connection limits.

Video generation and website generation are not shipped in this version. The existing
MCP video route returned a refunded upstream model error during QA. Website
generation has no suitable public API in the current Cormak contract.

The plugin calls `https://mcp.cormak.app` from the Dify runtime. See
[privacy](PRIVACY.md) for what it transmits.

Support: [support@cormak.app](mailto:support@cormak.app).

## Develop from source

Install `requirements.txt` in Python 3.12 or 3.13. From the source repository
root, run `PYTHONPATH=. python -m unittest discover -s tests`. The importable
read-only connection workflow is `workflows/balance-check.yml`. The source
setup helpers, tests, workflow, and experimental video adapter are excluded
from the `.difypkg`. Build the package with the official Dify CLI:
`dify plugin package . -o cormak_agents-0.1.2.difypkg`.
