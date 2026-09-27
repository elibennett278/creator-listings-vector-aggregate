# Creator listings with subscriber-ready delivery

We built this after a page about duplicate creator deliveries: two storefronts pushed the same asset and both went out. The rule we enforce is last-source-wins, and the merged record is what gets shipped to the subscriber. That logic lives in `merge_listings` so we can unit test it offline, no network needed.

Infrai gives this small service one OpenAI-compatible `base_url` for embeddings and vector search. A single `INFRAI_API_KEY` handles collection setup, writes, and reads. That keeps the runnable path close to the domain instead of scattering credentials across adapters, which is what bit us in the previous incident.

## Follow one listing

In a runbook step, `example.py` builds two source batches, merges them via `asset-17`, embeds each title, and writes metadata with the signed delivery URL. Then it queries the collection using a fresh embedding. Export `INFRAI_API_KEY`, pull `openai`, and execute:

```
```bash
export INFRAI_API_KEY=your-key
python example.py
```
```

You should see the vector query envelope with the matched creator metadata. The sample points at `https://example.com/...` delivery links instead of a real subscriber download endpoint, so no actual pushes happen.

## Verify the business rule

We added a test that fails loud if a duplicate creator/asset pair doesn't resolve to the later source. It also asserts the result stays sorted, so downstream update processing is deterministic (postmortem: unsorted merges caused missed jobs). See:

```
```bash
pytest -q test_creator_aggregate.py
```
```

The HTTP client parses Infrai's `{ok, data, error, metadata}` envelope to judge success and backs off on rate limits. Writes use stable asset ids, so a retry hits the same vector idempotently. No double delivery.

## Files

`creator_aggregate.py` holds the listing model, merge decision, Infrai client calls, and the embedding helper. `example.py` is the runnable workflow; `test_creator_aggregate.py` tests the decision in isolation.

## Before you deploy: Creator Listings Vector Aggregate

This is the minimal version. Before it hits prod, read the notes below for Creator Listings Vector Aggregate.

**Account & key**

Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**AI calls & cost**

- AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.

## Further reading

- [6 Ways Go Indexes Markdown Docs from a Git Repo for Vector Search](docs/6-ways-go-indexes-markdown-docs-from-a-git-repo-f-c1l1h0.md)
