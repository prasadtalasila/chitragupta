from chitragupta import chroma_paging


class PagingCollection:
    def __init__(self, count, page_cap=None):
        self.rows = [(f"id{i}", {"citekey": f"k{i}"}) for i in range(count)]
        self.page_cap = page_cap
        self.calls = []

    def get(self, where=None, include=None, limit=None, offset=None):
        self.calls.append({"where": where, "include": include, "limit": limit, "offset": offset})
        page = self.rows[offset or 0 :][:limit]
        if self.page_cap is not None:
            page = page[: self.page_cap]
        return {"ids": [i for i, _ in page], "metadatas": [m for _, m in page]}


def test_a_collection_smaller_than_one_page_comes_back_whole():
    collection = PagingCollection(3)
    assert chroma_paging.all_rows(collection)["ids"] == ["id0", "id1", "id2"]


def test_a_collection_spanning_pages_comes_back_whole_and_in_order(monkeypatch):
    monkeypatch.setattr(chroma_paging, "PAGE_SIZE", 2)
    collection = PagingCollection(5)

    rows = chroma_paging.all_rows(collection)

    assert rows["ids"] == [f"id{i}" for i in range(5)]
    assert [m["citekey"] for m in rows["metadatas"]] == [f"k{i}" for i in range(5)]


def test_a_short_page_does_not_skip_the_rows_behind_it(monkeypatch):
    monkeypatch.setattr(chroma_paging, "PAGE_SIZE", 3)
    collection = PagingCollection(5, page_cap=2)

    assert chroma_paging.all_rows(collection)["ids"] == [f"id{i}" for i in range(5)]


def test_the_criteria_reach_the_collection_unchanged(monkeypatch):
    monkeypatch.setattr(chroma_paging, "PAGE_SIZE", 10)
    collection = PagingCollection(1)

    chroma_paging.all_rows(collection, where={"citekey": "a2024"}, include=["metadatas"])

    assert collection.calls[0] == {
        "where": {"citekey": "a2024"},
        "include": ["metadatas"],
        "limit": 10,
        "offset": 0,
    }
