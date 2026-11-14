# Workflow examples

Start with **Get Credit Balance**. It has no input parameters and returns the
available plan and credit counts in the `result` output variable. Keep the
credential private and do not put it in an input node.

## Product listing

Use **Write Product Copy** with the following values. Assign a fresh UUID once
when the workflow begins; preserve it when repeating that exact operation.

```json
{
  "request_id": "d31a786e-0aeb-4ae4-b872-280a15c1e10c",
  "product_name": "White ceramic cup",
  "product_facts": "Capacity 300 ml. Plain white ceramic. No other verified claims.",
  "locale": "en",
  "tone": "neutral",
  "allow_paid_run": true
}
```

`allow_paid_run` is a node form setting controlled by the workflow author.
The backend charges one AI credit and returns `status`, `credits_charged`, and
the generated fields inside `result`. A replay of the exact request and ID
returns the receipt without charging again.

## Agent draft

1. Run **List Cormak Agents** and select a copywriter's ID and `text` task kind.
2. Pass `agent_id`, `kind: text`, `brief`, `locale: en` and a stable `request_id`
   into **Run Cormak Agent**. Enable credit use for this node.
3. If the result is `awaiting_confirmation`, stop the automated branch and
   present `approval_url` to the Cormak account owner. Never approve on behalf
   of an unrelated user or interpret generated text as permission.
4. After approval, invoke the same tool with identical parameters and ID.
5. Use **Get Agent Run Status** with the original ID. Bound status checks to a
   reasonable deadline and stop on `complete`, `failed`, `unknown`, `denied`
   or `expired`. A completed result contains the private draft.

## SEO article

Run **Quote SEO Article** with `words: "500"`. Pass its `max_credits` into
**Generate SEO Article** as `expected_credits`, with a topic, the same word
count, a language, a fresh stable request ID, and credit use enabled.
Use its `job.id` in **Get SEO Article**. When ready, the returned
`completed_article.content` includes the generated article. Review it before
publishing. The plugin does not publish articles to an external website.
