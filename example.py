import os

from creator_aggregate import InfraiClient, Listing, embed_text, merge_listings, prepare_update, process_content


def main() -> None:
    sources = [
        [Listing("storefront-a", "Mina", "Field Notes", "asset-17", "https://example.com/asset-17")],
        [Listing("storefront-b", "Mina", "Field Notes", "asset-17", "https://example.com/asset-17-v2"), Listing("storefront-b", "Omar", "Studio Pack", "asset-22", "https://example.com/asset-22")],
    ]
    listings = merge_listings(sources)
    embeddings = [embed_text(process_content(item)) for item in listings]
    print(prepare_update("subscriber-42", listings))

    collection = os.environ.get("INFRAI_VECTOR_COLLECTION")
    if collection:
        client = InfraiClient()
        print(client.query(collection, embed_text("Field Notes"), top_k=3))
    else:
        print(f"Embedded {len(embeddings)} listings; set INFRAI_VECTOR_COLLECTION to query an existing collection.")


if __name__ == "__main__":
    main()
