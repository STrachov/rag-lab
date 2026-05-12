# Roadmap

## Phase 1: Project Skeleton

- repository structure
- docs
- basic FastAPI app
- PostgreSQL application database foundation
- React/Vite placeholder UI
- project, data asset, parameter set, and saved experiment CRUD foundation

## Phase 2: Data Preparation

- upload source data assets
- store generated safe filenames and manifest snapshots
- inspect PDF text-layer, page, image, encryption, and scan-likelihood signals
- edit assets by adding and deleting files
- download files by original filename
- prepare source assets into prepared versions
- support converter parameter snapshots:
  - pymupdf_text
  - docling
  - ocrmypdf_tesseract
  - marker
  - mineru
  - custom_vlm

## Phase 3: Basic RAG Runtime

- chunk prepared data using the selected prepared data asset manifest
- embed chunks
- index in Qdrant
- retrieve top-k chunks
- track derived cache entries

## Phase 4: Answer Generation And Citations

- prompt rendering
- answer generation
- citation extraction
- not-found behavior
- debug traces controlled by debug level

## Phase 5: Evaluation

- ground truth set format
- retrieval metrics
- answer/citation metrics
- latency/cost metrics
- saved experiment metrics

## Phase 6: Comparison And Recipes

- compare saved experiments by metrics
- promote validated parameter snapshots
- export production recipe

## Later

- reports derived from saved experiment metrics
- hybrid search
- reranking
- contextual chunks
- parent-child retrieval
- OCR-to-RAG bridge
- GraphRAG only if explicitly needed
