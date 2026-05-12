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
counts
hashes
latency
metrics
```

## Anonymization

Replace names, addresses, account numbers, emails, signatures, and phone numbers before using documents in demos.
