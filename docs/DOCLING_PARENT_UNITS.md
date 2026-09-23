# Docling parent-unit text coverage

Preparation saves Docling's `md_content` as Markdown and separately builds page/chapter units
from `json_content`. Parent units do not parse the Markdown.

The previous extractor indexed only `texts` and `tables`, then visited only direct
`body.children`. Any group reference was ignored whenever at least one direct text/table
reference was found. Both page and chapter builders received that incomplete element list.

The saved Wheeler document demonstrates the failure: immediately after `#/texts/0`, the body
references `#/groups/0`, a `form_area` containing 39 text children. Those children include the
cover title, company identifier and trading symbols. They have valid page-1 provenance;
neither a missing bounding box nor a text-label filter caused their loss. Nested lists and
key/value groups were affected by the same shallow traversal.

The extractor now follows body references recursively in child order, including nested groups
and item children. Linked captions are visited after their owner when not already encountered.
Each self-reference is emitted once; distinct items with equal text are not deduplicated.
All referenced textual labels use `text`/`orig`; tables retain their existing grid-to-Markdown
rendering. Container names, raw document metadata, and image pixels are not synthesized as text.
The body tree defines prepared content; the separate furniture tree and unreferenced inventory
entries are not appended in arbitrary order. Textual headers/footers referenced by the body
remain included regardless of label.

Page attribution uses the first valid positive page number in an item's provenance list and
does not require a bounding box. Text without usable page provenance or dangling body references
fails explicitly instead of silently producing incomplete parent files. Existing primary-page
handling of multi-page items is unchanged. Page/chapter ID construction, chapter grouping and
its page fallback, recursive chunking, token counting and parent restoration are unchanged.
Newly recovered section headings may naturally introduce additional chapters.

Regenerating parent files from the saved Wheeler Docling JSON recovered `FORM 10-K`,
`WHEELER REAL ESTATE INVESTMENT TRUST, INC.`, `45-2681082` and `WHLRP` on page 1 and in
chapter source ranges including page 1. The traversal returned 1000 unique content references,
including the document's tables. This check reused the saved response; it did not rerun live OCR.

Existing prepared assets and their derived chunks/indexes must be regenerated to use the fix.
No stored assets are rewritten automatically. Tests use synthetic nested form/key-value groups,
tables, list items, captions and unlabelled text, and exercise both preparation and recursive
chunking boundaries. No source document is included in test fixtures.

Verification: focused `tests/test_parent_units.py tests/test_projects_api.py`: **79 passed**
(5.00 s); full pytest: **198 passed** (21.92 s); `git diff --check`: passed.
Frontend unchanged; no frontend build or live Docling/OCR run.
