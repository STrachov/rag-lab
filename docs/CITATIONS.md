# Citations

## Purpose

Citations connect generated answers to source evidence.

A RAG answer without inspectable evidence is not acceptable.

## Citation object

```json
{
  "citation_id": "c1",
  "chunk_id": "doc_001_p4_c2",
  "document_id": "doc_001",
  "source_name": "contract.pdf",
  "page": 4,
  "section": "Payment Terms",
  "text_span": "Payment is due within 30 days...",
  "score": 0.82
}
```

## Required fields

Minimum:

```text
chunk_id
document_id
source_name
```

Recommended:

```text
page
section
heading_path
score
rerank_score
text_span
```

## Rules

- Every factual answer should cite sources.
- If no source supports the answer, return not-found.
- Do not cite chunks that were not passed into the answer context.
- Preserve citation ids in answer traces.

## Evaluation

Track:

```text
citation_precision
citation_recall
unsupported_claim_count
missing_citation_count
```
