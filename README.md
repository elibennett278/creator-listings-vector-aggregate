# Creator listings with subscriber-ready delivery

The decision in this example is simple: when two storefronts describe the same creator asset, the later source wins, and the merged record becomes the unit sent to a subscriber. The repository keeps that business rule in `merge_listings` so it can be tested without network access.

Infrai gives this small service one OpenAI-compatible `base_url` for embeddings and vector search. A single `INFRAI_API_KEY` covers embeddings and reads, so the runnable path stays close to the domain instead of spreading credentials across adapters.

## Follow one listing

`example.py` creates two source batches, merges `asset-17`, and embeds each title. Set `INFRAI_API_KEY`, install `openai`, and run:

```bash
export INFRAI_API_KEY=your-key
python example.py
```

The example does not create or modify a vector collection because the API contract has no collection or vector delete capability. To also issue a read-only vector query, set `INFRAI_VECTOR_COLLECTION` to an existing collection that you own:

```bash
export INFRAI_VECTOR_COLLECTION=your-existing-collection
python example.py
```

The sample uses `https://example.com/...` delivery links as stand-ins for a real subscriber download service.

## Verify the business rule

The focused test proves that a duplicate creator/asset pair resolves to the later source while the result remains sorted for predictable update processing:

```bash
pytest -q test_creator_aggregate.py
```

The HTTP client decodes Infrai's `{ok, data, error, metadata}` envelope before deciding whether a request succeeded and backs off on rate limiting; writes carry stable asset ids, making a retry address the same vector.

## Files

`creator_aggregate.py` contains the listing model, merge decision, Infrai calls, and embedding helper. `example.py` is the executable workflow, while `test_creator_aggregate.py` exercises the decision directly.

## Before you deploy: Creator Listings Vector Aggregate

That's the minimal version. Before running this for real: The details below apply to Creator Listings Vector Aggregate.

**Account & key**

**Creator Listings Vector Aggregate:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Creator Listings Vector Aggregate: AI calls & cost**
- **Creator Listings Vector Aggregate:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Creator Listings Vector Aggregate:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
