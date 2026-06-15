# Data Policy

## Do not commit

Never commit:

```text
real client documents
contracts
invoices
medical records
legal documents
bank statements
personal data
API keys
auth headers
private URLs
```

## Allowed in git

```text
synthetic demo documents
anonymized examples
schema examples
config examples
prompt templates
empty folders with .gitkeep
```

## Local data

Use:

```text
data/
```

The `data/` directory should usually be gitignored except for tiny synthetic samples.

## Logging rules

Do not log:

```text
full document text
secrets
auth headers
private URLs
PII
PHI
financial account numbers
```

Safe to log:

```text
project_id
data_asset_id
data_asset_manifest_hash
document_id
chunk_id
experiment_id
config_id
cache_key
collection_name
index_mode
counts
hashes
latency
metrics
dense_score
sparse_score
rerank_score
```

Chunk text is sensitive derived data. Chunking preview may show full text for the returned preview
chunks so users can inspect boundaries; retrieval/reranking preview should show clipped text previews
for debugging. Do not commit derived cache files, GT authoring packs, screenshots containing client
text, or paste full retrieved chunks into logs. Local rerankers may read full materialized chunk text
for scoring. Remote reranker catalog entries, such as Voyage rerank models and the OpenAI
LLM-as-reranker, send the query and current candidate chunk text to the provider API when explicitly
selected in retrieval/reranking preview.

GT authoring packs contain prepared text and full chunk text. Treat them like derived client cache:
keep them local, do not commit them, and do not upload them to external tools unless the data owner
has approved that workflow.

## Anonymization

Replace names, addresses, account numbers, emails, signatures, and phone numbers before using documents in demos.
