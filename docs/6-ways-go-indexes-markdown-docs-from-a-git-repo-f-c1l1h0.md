# 6 Ways Go Indexes Markdown Docs from a Git Repo for Vector Search

Retrieval quality usually improves when a chunk carries enough local context, while latency usually improves when the index contains fewer, smaller records. To index Markdown docs from a Git repo for vector search, use section boundaries rather than arbitrary token windows, then measure retrieval against real property-management questions before tuning chunk size. **Short answer: parse headings, preserve document identity and source revision, split oversized sections with overlap, embed in bounded batches, and replace each file's old chunks atomically.**

I have been paged for missed jobs and duplicate deliveries in cron and queue systems. The lesson transfers directly to repository ingestion: a successful embedding call does not prove that the index represents the current commit. One retry can leave duplicate chunks; one missed deletion can return an obsolete pet policy after the lease handbook changed. The invariant is stricter: for a given repository, path, and commit, every expected chunk exists exactly once, and no superseded chunk remains searchable.

## 1. How should a Git repo index Markdown docs for vector search?

Markdown already contains an author-supplied hierarchy. A property manager may place `Emergency maintenance` under `Resident responsibilities`, followed by a separate `After-hours contacts` section. A blind fixed-width splitter can join unrelated sections or detach an exception from its heading. Heading-aware chunks retain that meaning.

Boundaries matter.

Start with one chunk per section and prepend the heading trail to the text sent for embedding. Keep the path and heading trail as stored metadata too. For a short document, indexing the entire file may give better context and fewer vector comparisons. For a long policy manual, whole-file embedding can blur distinct topics and make precise citations difficult. There is no universal character count that resolves both cases.

An oversized section still needs a second split. Prefer paragraph boundaries, then sentences, and use a small overlap only at those secondary boundaries. Overlap is insurance against a thought crossing the split; excessive overlap creates near-duplicates that can occupy several top results without adding evidence.

## 2. Give every chunk a stable identity

A chunk ID should describe logical content, not the time a worker happened to process it. Hash a normalized repository identifier, relative path, heading trail, and ordinal within that section. Store the source commit separately. This makes retries idempotent while still exposing exactly which revision produced a result.

Do not use the text hash alone. Identical boilerplate such as an equal-housing notice can occur in several buildings, and those copies may have different access rules or canonical URLs. Path alone is insufficient too, because one file produces several chunks.

The useful record is small:

| Field | Purpose | Failure it exposes |
|---|---|---|
| `chunk_id` | Stable upsert key | Duplicate retry output |
| `repo` and `path` | Source ownership | Cross-repository collision |
| `commit` | Revision trace | Stale searchable content |
| `heading` and `ordinal` | Local position | Broken citations or reordering |
| `content_hash` | Change detection | Unnecessary re-embedding |
| `text` | Retrieval evidence | Results that cannot be inspected |

Keep the original text. A vector by itself cannot support a useful citation or a post-incident comparison.

## 3. Make replacement a commit-scoped operation

The dangerous sequence is delete-old, then embed-new. A failure in the middle creates a temporary hole. Upsert-new, then delete-old avoids the hole but can briefly expose both revisions unless queries filter on an active generation.

Retries happen.

Use a generation marker. Build all chunks for a commit under an inactive generation, verify the expected count, switch the repository's active generation, and only then garbage-collect older generations. The switch must be atomic in the metadata store used by the query path. If that store cannot provide an atomic compare-and-swap or transaction, serialize publishers per repository and accept that the guarantee is weaker.

This preventative Go path focuses on the part workers commonly get wrong. Parsing and embedding are injected interfaces, so the control flow does not depend on a particular vector database or model provider.

```go
package ingest

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
)

type Chunk struct {
	ID, Repo, Path, Commit, Heading, Text string
	Ordinal                              int
	Vector                               []float32
}

type Embedder interface {
	Embed(context.Context, []string) ([][]float32, error)
}

type Index interface {
	UpsertGeneration(context.Context, string, []Chunk) error
	CountGeneration(context.Context, string) (int, error)
	Activate(context.Context, string, string, string) error
	DeleteOlderGenerations(context.Context, string, string) error
}

func stableID(repo, path, heading string, ordinal int) string {
	sum := sha256.Sum256([]byte(fmt.Sprintf("%s\x00%s\x00%s\x00%d", repo, path, heading, ordinal)))
	return hex.EncodeToString(sum[:])
}

func Publish(ctx context.Context, idx Index, emb Embedder, generation string, chunks []Chunk) error {
	texts := make([]string, len(chunks))
	for i := range chunks {
		chunks[i].ID = stableID(chunks[i].Repo, chunks[i].Path, chunks[i].Heading, chunks[i].Ordinal)
		texts[i] = chunks[i].Heading + "\n\n" + chunks[i].Text
	}

	vectors, err := emb.Embed(ctx, texts)
	if err != nil {
		return fmt.Errorf("embed generation %s: %w", generation, err)
	}
	if len(vectors) != len(chunks) {
		return fmt.Errorf("vector count %d does not match chunk count %d", len(vectors), len(chunks))
	}
	for i := range chunks {
		chunks[i].Vector = vectors[i]
	}

	if err := idx.UpsertGeneration(ctx, generation, chunks); err != nil {
		return fmt.Errorf("upsert generation %s: %w", generation, err)
	}
	count, err := idx.CountGeneration(ctx, generation)
	if err != nil || count != len(chunks) {
		return fmt.Errorf("verify generation %s: stored=%d expected=%d: %w", generation, count, len(chunks), err)
	}
	if len(chunks) == 0 {
		return fmt.Errorf("refuse to activate empty generation %s", generation)
	}

	repo, commit := chunks[0].Repo, chunks[0].Commit
	if err := idx.Activate(ctx, repo, generation, commit); err != nil {
		return fmt.Errorf("activate generation %s: %w", generation, err)
	}
	return idx.DeleteOlderGenerations(ctx, repo, generation)
}
```

Production code should also reject mixed repositories or commits in one call, place explicit limits on batch size and input bytes, and retain the previous generation until rollback is no longer needed. Empty repositories need a deliberate tombstone publication path rather than the guard shown above.

## 4. Treat deletions as data

Incremental ingestion that only notices modified files accumulates ghosts. A renamed `parking.md` looks like one addition and one deletion; without the deletion half, both versions remain eligible for retrieval. Compare the current Git tree with the last published tree, or rebuild a complete generation from the target commit.

Full-generation rebuilds are operationally plain and often appropriate for a modest documentation repository. Incremental updates reduce embedding work on large repositories, but they require a manifest, deletion handling, and careful recovery when publication stops halfway. **Choose incremental ingestion only after the full rebuild exceeds a measured latency or resource budget.** Complexity is part of the latency budget because recovery work delays freshness.

Submodules, symbolic links, binary files, and generated Markdown need explicit policy. Ignoring them silently is how expected chunk counts drift. Record exclusions with a reason and include excluded-file counts in the run summary.

## 5. Test retrieval with property questions, not chunk statistics

Chunk count, embedding duration, and index size are health signals. They do not measure whether a leasing specialist can find the right clause. Build a small evaluation set of questions with relevant paths and passages: who handles an overflowing toilet after hours, what documentation supports an assistance-animal request, when late fees apply, and which parking rules belong to a particular building.

For each candidate chunking policy, measure whether a relevant passage appears within the first few results and record query latency as a distribution, not a single average. Inspect failures. A miss caused by a vague query needs different treatment from a miss caused by a heading detached from its exception.

Keep access control outside the vector score. Filter candidates by property, portfolio, document class, and caller authorization before returning text. Metadata filtering behavior differs across index implementations, so verify that filtering occurs during retrieval rather than after an unauthorized candidate has already left the trusted boundary.

The RAG paper describes combining retrieved passages with generation, but generation is downstream of this evaluation. First prove retrieval. Otherwise a fluent answer can hide a bad index.

## 6. Operate the pipeline like a delivery system

Queue messages should identify a repository and immutable commit, not merely say “refresh.” Coalesce older pending commits when a newer commit supersedes them, but never interrupt the active publication in a way that can leave its generation ambiguous. Retries need exponential backoff and a terminal dead-letter state with enough context to replay safely.

Watch four boundaries: Git read, Markdown parse, embedding, and publication. Emit duration and failure counts for each, plus source files discovered, files excluded, chunks expected, chunks stored, active commit, and generation age. Alert on stale active commits and repeated terminal failures. A worker being alive is weak evidence.

Roll out a changed splitter by dual-building a candidate generation and running the same retrieval set against both generations. Promote only when the quality change and latency change are understood. **The decision rule is evidence-based: accept slower retrieval only when it fixes important misses, and accept smaller chunks only when they preserve the clauses needed to answer and cite the question.**

These limitations define the method's boundary. It does not apply unchanged to source-code search, where syntax trees and symbol relationships provide better boundaries than Markdown headings, and it needs adaptation for scanned leases because OCR quality becomes an upstream constraint. A generation rebuild also trades extra storage and embedding work for a cleaner publication boundary; a tiny repository may need neither a queue nor incremental processing, while a repository too large to rebuild within its freshness target needs the manifest complexity described above. For ordinary repository-hosted property policies, stable identity, generation publication, and question-level evaluation form a defensible baseline.

## Sources

- https://arxiv.org/abs/2005.11401
- https://spec.commonmark.org/
- https://git-scm.com/docs/git-diff-tree
- https://www.rfc-editor.org/rfc/rfc8785
