"""Explicit adapters from Dify inputs to Cormak's published contracts."""

import re

from cormak import CormakError, identifier, record

AGENT_TASKS = {
    "support": ("faq",),
    "sales": ("objections", "qualification"),
    "smm": ("calendar", "post", "campaign"),
    "copywriter": ("text", "rewrite", "series"),
    "marketplace": ("listing", "audit"),
}
SEO_LENGTHS = {"500": 500, "1000": 1000, "1500": 1500, "2000": 2000, "3000": 3000}


def text(params, name, maximum, *, minimum=1, default=None):
    value = params.get(name, default)
    if not isinstance(value, str):
        raise CormakError(f"invalid_{name}")
    value = value.strip()
    if not minimum <= len(value.encode("utf-16-le", errors="surrogatepass")) // 2 <= maximum or "\0" in value:
        raise CormakError(f"invalid_{name}")
    return value


def select(params, name, choices, default):
    value = params.get(name, default)
    if not isinstance(value, str) or value not in choices:
        raise CormakError(f"invalid_{name}")
    return value


def request_id(params):
    return identifier(params.get("request_id"))


def paid_request(params):
    if params.get("allow_paid_run") is not True:
        raise CormakError("paid_run_disabled")
    return request_id(params)


def account(client, _params):
    value = client.mcp("get_account")
    return {key: value[key] for key in ("plan", "available_ai_credits", "video_credits") if key in value}


def list_agents(client, _params):
    value = client.mcp("list_employees")
    rows = value.get("items")
    if not isinstance(rows, list):
        raise CormakError("invalid_response")
    return {"agents": [
        {"agent_id": row["id"], "name": row["name"], "role": row["role"], "task_kinds": list(AGENT_TASKS[row["role"]])}
        for row in rows if isinstance(row, dict) and isinstance(row.get("role"), str)
        and row["role"] in AGENT_TASKS and isinstance(row.get("id"), str)
        and isinstance(row.get("name"), str) and row.get("archived") is False
    ]}


def start_agent(client, params):
    operation_id = paid_request(params)
    agent_id = identifier(params.get("agent_id"))
    kind = text(params, "kind", 40)
    brief = text(params, "brief", 6000)
    locale = select(params, "locale", ("en", "ru", "de", "es", "ko"), "en")
    agents = list_agents(client, {})["agents"]
    if not any(agent["agent_id"] == agent_id and kind in agent["task_kinds"] for agent in agents):
        # Use the same ownership-protected read for agents outside the first page.
        selected = client.mcp("get_employee", employee_id=agent_id).get("items", [])
        if not isinstance(selected, list) or not any(
            isinstance(row, dict) and row.get("id") == agent_id and row.get("archived") is False
            and isinstance(row.get("role"), str) and kind in AGENT_TASKS.get(row["role"], ())
            for row in selected
        ):
            raise CormakError("unsupported_agent_task")
    return client.mcp("run_employee_task", request_id=operation_id, employee_id=agent_id,
                      kind=kind, brief=brief, locale=locale)


def agent_status(client, params):
    return client.mcp("get_operation", request_id=request_id(params))


def start_image(client, params):
    return client.mcp(
        "generate_image", request_id=paid_request(params), confirm_spend=True,
        prompt=text(params, "prompt", 2000),
        aspect_ratio=select(params, "aspect_ratio", ("1:1", "16:9", "9:16", "4:3", "3:4"), "1:1"),
        style=select(params, "style", ("gold", "neon", "vector", "realistic", "logo"), "realistic"),
    )


def media_status(client, params):
    return client.mcp("get_generation", request_id=request_id(params))


def product_copy(client, params):
    operation_id = paid_request(params)
    locale = text(params, "locale", 16, default="en")
    if not re.fullmatch(r"[a-z]{2,3}(?:[_-][A-Za-z0-9]{2,8}){0,2}", locale):
        raise CormakError("invalid_locale")
    return client.store(
        "fill_text", request_id=operation_id, locale=locale,
        product={"name": text(params, "product_name", 200, minimum=2), "description": text(params, "product_facts", 6000)},
        options={"fields": ["title", "description", "short_description", "seo"],
                 "tone": select(params, "tone", ("neutral", "friendly", "premium", "expert", "playful", "minimal"), "neutral")},
    )


def seo_quote(client, params):
    words = SEO_LENGTHS[select(params, "words", SEO_LENGTHS, "1000")]
    return client.blog("quote", words=words, count=1, with_images=False)


def start_seo(client, params):
    operation_id = paid_request(params)
    language = text(params, "locale", 12, default="en")
    if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})?", language):
        raise CormakError("invalid_locale")
    expected = params.get("expected_credits")
    if isinstance(expected, bool) or not isinstance(expected, (int, float)) or not 0 <= expected <= 100 or int(expected) != expected:
        raise CormakError("invalid_expected_credits")
    topic = text(params, "topic", 200, minimum=3)
    keywords = text(params, "keywords", 500, minimum=0, default="")
    return client.blog(
        "start", request_id=operation_id, expected_credits=int(expected),
        brief={"prompt": topic, "mode": "topic", "language": language, "with_images": False,
               "words": SEO_LENGTHS[select(params, "words", SEO_LENGTHS, "1000")],
               "style": select(params, "style", ("expert", "sales", "informational", "conversational"), "informational"),
               "audience": text(params, "audience", 300, minimum=0, default=""), "keywords": keywords},
        topics=[{"topic": topic, "keywords": keywords}],
    )


def seo_status(client, params):
    job_id = identifier(params.get("job_id"))
    value = client.blog("job", job_id=job_id)
    articles = value.get("articles")
    if not isinstance(articles, list) or len(articles) != 1:
        raise CormakError("invalid_response")
    article = record(articles[0])
    if article.get("status") == "complete":
        result = client.blog("article", article_id=identifier(article.get("id")))
        value["completed_article"] = record(result.get("article"))
    return value
