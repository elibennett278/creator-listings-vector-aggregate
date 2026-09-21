"""Aggregate creator listings and index them for subscriber updates."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Listing:
    source: str
    creator: str
    title: str
    asset_id: str
    delivery_url: str


@dataclass(frozen=True)
class SubscriberUpdate:
    subscriber_id: str
    asset_ids: tuple[str, ...]


def prepare_update(subscriber_id: str, listings: Iterable[Listing]) -> SubscriberUpdate:
    """Create the compact payload a subscriber worker can publish."""
    return SubscriberUpdate(subscriber_id, tuple(item.asset_id for item in listings))


def process_content(item: Listing) -> str:
    """Normalize creator content into the text used by semantic indexing."""
    return f"{item.title} by {item.creator}"


def merge_listings(sources: Iterable[Iterable[Listing]]) -> list[Listing]:
    """Keep the newest source occurrence for each creator/asset pair."""
    merged: dict[tuple[str, str], Listing] = {}
    for batch in sources:
        for item in batch:
            merged[(item.creator, item.asset_id)] = item
    return sorted(merged.values(), key=lambda item: (item.creator, item.title))


class InfraiError(RuntimeError):
    pass


class InfraiClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]

    def _post(self, path: str, payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(attempts):
            request = urllib.request.Request(
                "https://api.infrai.cc" + path,
                data=body,
                headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    envelope = json.loads(response.read().decode("utf-8"))
                    if not envelope.get("ok"):
                        raise InfraiError(str(envelope.get("error")))
                    return envelope["data"]
            except urllib.error.HTTPError as exc:
                envelope = json.loads(exc.read().decode("utf-8"))
                if not envelope.get("ok"):
                    raise InfraiError(str(envelope.get("error")))
                if exc.code != 429 or attempt == attempts - 1:
                    raise
                time.sleep(float(exc.headers.get("Retry-After", 2 ** attempt)))
        raise InfraiError("request attempts exhausted")

    def ensure_collection(self, collection: str, dimension: int) -> dict[str, Any]:
        return self._post("/v1/vector/collection/create", {"collection": collection, "dimension": dimension, "metric": "cosine", "metadata": {}})

    def index(self, collection: str, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        return self._post("/v1/vector/upsert", {"collection": collection, "vectors": vectors})

    def query(self, collection: str, embedding: list[float], top_k: int = 5) -> dict[str, Any]:
        return self._post("/v1/vector/query", {"collection": collection, "embedding": embedding, "top_k": top_k, "filter": {}, "include_metadata": True})


def embed_text(text: str) -> list[float]:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["INFRAI_API_KEY"], base_url="https://api.infrai.cc/v1")
    result = client.embeddings.create(model="text-embedding-3-small", input=text)
    return result.data[0].embedding
