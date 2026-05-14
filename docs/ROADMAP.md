# Roadmap

## Phase 1: Project Skeleton

- repository structure
- docs
- basic FastAPI app
- PostgreSQL application database foundation
- React/Vite placeholder UI
- project, data asset, parameter set, and saved experiment CRUD foundation
- categorized parameter sets with protected deletion

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
- expose preparation methods through a backend catalog
- store Docling Markdown and full Docling JSON as prepared asset files

## Phase 3: Basic RAG Runtime

- backend-driven chunking strategy catalog
- chunking preview over prepared data assets
- native and LangChain-backed chunking strategies
- materialize chunks from a prepared data asset and chunking snapshot
- store normalized chunk JSONL as `DerivedCache(cache_type="chunks")`
- expose backend-driven embedding and sparse model catalogs
- embed chunks with local SentenceTransformers models
- build local BM25-style sparse vectors and stats
- index in Qdrant with named dense and sparse vectors
- retrieve top-k chunks in dense, sparse, or hybrid mode
- merge hybrid retrieval previews with reciprocal rank fusion
- expose backend-driven reranker model catalogs
- rerank retrieval preview candidates with local cross-encoder models
- track ready and failed derived cache entries

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
- advanced hybrid search variants
- advanced reranking calibration
- contextual chunks
- parent-child retrieval
- OCR-to-RAG bridge
- GraphRAG only if explicitly needed
