from creator_aggregate import Listing, merge_listings, prepare_update


def test_latest_source_wins_and_results_are_stable():
    old = Listing("a", "Mina", "Field Notes", "17", "old")
    fresh = Listing("b", "Mina", "Field Notes", "17", "fresh")
    other = Listing("b", "Omar", "Studio Pack", "22", "pack")
    assert merge_listings([[old], [fresh, other]]) == [fresh, other]
    assert prepare_update("reader-1", [fresh, other]).asset_ids == ("17", "22")
