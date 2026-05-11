# API Contracts

## Purpose

Planned API surface for RAG Lab.

## Error shape

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

## Datasets

```http
GET  /v1/datasets
POST /v1/datasets
GET  /v1/datasets/{dataset_id}
POST /v1/datasets/{dataset_id}/documents
GET  /v1/datasets/{dataset_id}/documents
```

## Chunking and indexing

```http
POST /v1/datasets/{dataset_id}/chunk
GET  /v1/chunk-manifests/{chunk_manifest_id}
POST /v1/datasets/{dataset_id}/index
```

## Retrieval and answer

```http
POST /v1/retrieve
POST /v1/ask
```

## Eval sets

```http
GET  /v1/eval-sets
POST /v1/eval-sets
GET  /v1/eval-sets/{eval_set_id}
```

## Experiments

```http
POST /v1/experiments
POST /v1/experiments/{experiment_id}/run
GET  /v1/experiments/{experiment_id}
GET  /v1/experiments/{experiment_id}/result
```

## Reports and recipes

```http
POST /v1/experiments/{experiment_id}/report
GET  /v1/reports/{report_id}
POST /v1/experiments/{experiment_id}/promote-to-recipe
GET  /v1/recipes
GET  /v1/recipes/{recipe_id}
```

## Breaking-change rule

After implementation, treat endpoint renames, required-field changes, response-shape changes, and error-shape changes as breaking.
