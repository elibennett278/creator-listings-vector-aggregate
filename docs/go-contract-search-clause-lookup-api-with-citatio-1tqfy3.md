# Go Contract Search: Clause Lookup API with Citation-Safe Scheduling

Operational constraint: a clause hit is useless when its citation points to a superseded publishing agreement. **The practical choice is a versioned semantic-search API backed by idempotent ingestion, immutable source coordinates, and an EU-bound processing path.** Treat residency as a verified deployment property, not a region label.

TL;DR: For a gaming legal team looking up indemnity, territory, or termination language, schedule each contract revision as a uniquely keyed ingestion run. Publish its chunks atomically, return the exact document version and page or section with every result, and keep old revisions queryable but excluded by default. Evaluate the system on citation correctness and stale-version isolation before comparing ranking quality.

## How should a semantic search API handle contract clause lookup?

I have been paged by missed jobs and duplicate deliveries. That experience changes the design question: the dangerous boundary is not the embedding call; it is the handoff between a newly uploaded contract and the searchable corpus. A missed run leaves an executed amendment invisible. A duplicate run can create two apparently independent hits for the same clause, distort ranking, and make an answer look better supported than it is. Reordering is worse in a quieter way: revision B may finish first, revision A may arrive late, and a worker that blindly marks its own output active can roll the searchable contract backward without reporting an error. Every component can look healthy while counsel receives an obsolete termination clause with a plausible citation. The scheduler therefore has to carry revision order into the commit condition, not merely into a log field.

The invariant is narrow: one source revision produces one committed chunk set, and a query observes either the old complete set or the new complete set. Never half of each.

No partial publication.

For a studio handling publishing, localization, talent, and platform agreements, the source identity should include the matter, document, revision, and content digest. Filename is not identity. An overwrite named `publishing-agreement-final.pdf` must become a new revision rather than silently changing the evidence under an existing citation.

This is where retrieval-augmented generation helps but does not settle the operational problem. The RAG paper describes combining retrieved passages with generation for knowledge-intensive work; it does not make ingestion atomic or establish the legal meaning of a document version. Those controls belong around the retrieval system.

## Schedule the commit, not merely the embedding call

I first treated queue deduplication as the finish line. It is not. Deduplication can reduce repeated work, but retries still need to be correct after a worker stops between writing chunk 37 and marking the run complete.

Use a run key derived from stable input identity. Write chunks into a staging generation, validate that generation, then move one manifest pointer. The query path reads only the active generation. This is closer to a database publication step than a batch of unrelated vector writes.

```go
package ingest

import (
    "context"
    "crypto/sha256"
    "encoding/hex"
    "fmt"
)

type Chunk struct {
    Text       string
    Page       int
    Section    string
    StartByte  int
    EndByte    int
}

type Store interface {
    BeginGeneration(ctx context.Context, runKey string) (string, error)
    PutChunk(ctx context.Context, generation string, ordinal int, chunk Chunk) error
    Validate(ctx context.Context, generation string, expected int) error
    Activate(ctx context.Context, documentID, revision, generation string) error
}

func RunKey(documentID, revision string, source []byte) string {
    sum := sha256.Sum256(source)
    return fmt.Sprintf("%s:%s:%s", documentID, revision, hex.EncodeToString(sum[:]))
}

func Publish(ctx context.Context, store Store, documentID, revision string, source []byte, chunks []Chunk) error {
    generation, err := store.BeginGeneration(ctx, RunKey(documentID, revision, source))
    if err != nil {
        return err
    }
    for i, chunk := range chunks {
        if err := store.PutChunk(ctx, generation, i, chunk); err != nil {
            return err
        }
    }
    if err := store.Validate(ctx, generation, len(chunks)); err != nil {
        return err
    }
    return store.Activate(ctx, documentID, revision, generation)
}
```

`BeginGeneration` and `PutChunk` must be idempotent for the same run key and ordinal. `Activate` must compare the expected revision so that an older, slow job cannot replace a newer revision. The implementation may use a transaction, a conditional write, or another atomic metadata primitive; the contract matters more than the storage engine.

The worker should retry transient failures with bounded backoff, but retry count is not a correctness mechanism. Keep the source object and run record long enough to replay ingestion, and quarantine inputs that fail deterministic parsing. No citation should become visible until validation checks chunk count, source coordinates, and manifest completeness.

## Make grounding observable

Similarity scores do not prove grounding. A useful response record carries a result ID, document ID, revision, clause text, and source coordinates. If generation follows retrieval, preserve those result IDs through the answer so each claim can be traced to the retrieved evidence.

Measure the pipeline at its boundaries. Track upload-to-active latency, oldest unprocessed revision age, duplicate run attempts, failed publications, and queries served from a superseded revision. The last metric should be zero under the default filter. Alert on age and broken invariants, not raw queue depth alone; a large queue can drain, while one blocked amendment can remain legally significant.

A release test should include at least these cases:

1. The same revision is delivered twice. Only one active chunk set appears.
2. A worker stops after writing some chunks. Queries still see the previous complete generation.
3. Revision B finishes before revision A. A cannot become active afterward.
4. A clause moves to another page. The returned citation follows the new revision.
5. A user lacking matter access searches exact clause wording. No metadata, text, or count leaks across the authorization boundary.

Short tests catch expensive incidents.

## Residency is an evidence chain

For EU data residency, draw the data flow before evaluating an API: upload, object storage, parsing, embedding, vector storage, query logs, backups, telemetry, and support access. A regional vector index is insufficient if contract text or prompts cross the chosen boundary elsewhere. Record the approved region and processing policy with each ingestion run, then reject work that cannot satisfy them.

This decision has a trade-off. Strict regional isolation narrows the set of available processing paths and can complicate failover. For contract evidence, explicit degradation is preferable to silently routing through an unapproved location. The runbook should state whether an unavailable region pauses ingestion, serves the last active revision, or disables generated answers while retaining cited search.

Keep authorization outside ranking. Filter the candidate set by tenant, matter access, document status, and active revision before semantic scoring. Post-filtering a global nearest-neighbor result can reveal counts or timing and can also return too few authorized candidates.

## Compare systems with failure drills

Do not begin a selection exercise with a feature matrix. Give each candidate the same representative contracts, amendments, scanned pages, repeated boilerplate, and access rules. Then interrupt ingestion at controlled points and verify the observable outcome.

Score citation precision separately from retrieval relevance. A result can contain the right clause while citing the wrong revision or page. Reviewers should be able to open the exact source location, inspect surrounding language, and identify the ingestion run that published it. Record false matches between similar boilerplate across unrelated matters as their own failure class.

The advice changes for a static, public corpus with no access boundaries and no revisions. There, rebuilding an index in place may be acceptable because stale or partial visibility has limited consequence. Private gaming contracts are different: amendments arrive asynchronously, clauses repeat, and the citation is part of the answer. Scheduling semantics deserve first-class weight.

**Choose the system that preserves evidence identity under retry, reordering, and regional failure.** Ranking quality matters after that invariant holds.

## Sources

- https://arxiv.org/abs/2005.11401
