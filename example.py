from creator_aggregate import InfraiClient, Listing, embed_text, merge_listings, prepare_update, process_content


def main() -> None:
    sources = [
        [Listing("storefront-a", "Mina", "Field Notes", "asset-17", "https://example.com/asset-17")],
        [Listing("storefront-b", "Mina", "Field Notes", "asset-17", "https://example.com/asset-17-v2"), Listing("storefront-b", "Omar", "Studio Pack", "asset-22", "https://example.com/asset-22")],
    ]
    listings = merge_listings(sources)
    client = InfraiClient()
    client.ensure_collection("creator-listings", 1536)
    vectors = [{"id": item.asset_id, "values": embed_text(process_content(item)), "metadata": {"creator": item.creator, "title": item.title, "delivery_url": item.delivery_url}} for item in listings]
    client.index("creator-listings", vectors)
    print(prepare_update("subscriber-42", listings))
    print(client.query("creator-listings", embed_text("Field Notes"), top_k=3))


if __name__ == "__main__":
    main()
