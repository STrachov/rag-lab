# API Contracts

## Purpose

Planned API surface for RAG Lab.

## Error Shape

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

## Projects

```http
GET  /v1/projects
POST /v1/projects
GET  /v1/projects/{project_id}
```

## Data Assets

```http
GET  /v1/projects/{project_id}/data-assets
POST /v1/projects/{project_id}/data-assets
POST /v1/projects/{project_id}/data-assets/raw/upload
POST /v1/projects/{project_id}/data-assets/prepared/upload
```

Upload endpoints store files under project-scoped storage and create immutable data asset records after the files and manifest are written.

Prepared data uploads must include preparation provenance metadata. Saved experiments should reference prepared data assets, not raw data assets.

## Parameter Sets

```http
GET  /v1/projects/{project_id}/parameter-sets
POST /v1/projects/{project_id}/parameter-sets
```

## Ground Truth Sets

```http
GET  /v1/projects/{project_id}/ground-truth-sets
POST /v1/projects/{project_id}/ground-truth-sets
```

## Saved Experiments

```http
GET  /v1/projects/{project_id}/saved-experiments
POST /v1/projects/{project_id}/saved-experiments
```

## Metrics

Saved experiment results are metrics only. Metrics may be returned in:

```text
metrics_summary_json
MetricValue rows
```

## Derived Cache

Chunks, embeddings, Qdrant indexes, traces, prompts, and generated answers are not core API results. Future debug endpoints should make the cache/debug status explicit.

## Breaking-Change Rule

After implementation, treat endpoint renames, required-field changes, response-shape changes, and error-shape changes as breaking.
