from __future__ import annotations

import pytest

from app.models.api import SavedExperimentCreate
from app.services.evaluation import aggregate_metrics, build_slice_metrics, question_metadata_matches
from app.services.ground_truth import _canonicalize_ground_truth
from app.services.gt_authoring_pack import _ground_truth_schema


def _chunk_ground_truth() -> dict:
    return {
        "metadata": {"ground_truth_type": "chunk_level_qrels"},
        "questions": [
            {
                "expected_answer_type": "found",
                "question": "Question one?",
                "question_id": "q1",
                "relevant_chunks": [{"chunk_id": "chunk_1", "relevance": 3}],
            }
        ],
    }


def test_old_ground_truth_without_metadata_or_slices_remains_valid() -> None:
    canonical = _canonicalize_ground_truth(_chunk_ground_truth())

    assert "metadata" not in canonical["questions"][0]
    assert "evaluation_slices" not in canonical


def test_question_metadata_and_evaluation_slices_survive_canonicalization() -> None:
    payload = _chunk_ground_truth()
    payload["questions"][0]["metadata"] = {
        "source": "source_a",
        "difficulty": "hard",
        "tags": ["numeric", "multi_page"],
        "review_note": "preserved extension",
    }
    payload["evaluation_slices"] = [
        {"id": "source_a", "label": "Source A", "filter": {"source": ["source_a"]}},
    ]

    canonical = _canonicalize_ground_truth(payload)

    assert canonical["questions"][0]["metadata"] == payload["questions"][0]["metadata"]
    assert canonical["evaluation_slices"] == payload["evaluation_slices"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", 1),
        ("difficulty", ["hard"]),
        ("tags", "numeric"),
        ("tags", ["valid", 2]),
    ],
)
def test_question_metadata_rejects_invalid_supported_field_types(field: str, value: object) -> None:
    payload = _chunk_ground_truth()
    payload["questions"][0]["metadata"] = {field: value}

    with pytest.raises(ValueError, match=f"metadata.{field}"):
        _canonicalize_ground_truth(payload)


def test_duplicate_slice_id_is_rejected() -> None:
    payload = _chunk_ground_truth()
    payload["evaluation_slices"] = [
        {"id": "same", "label": "One", "filter": {"source": ["a"]}},
        {"id": "same", "label": "Two", "filter": {"source": ["b"]}},
    ]

    with pytest.raises(ValueError, match="Duplicate evaluation slice id"):
        _canonicalize_ground_truth(payload)


@pytest.mark.parametrize(
    "invalid_filter",
    ["source=a", {}, {"source": "a"}, {"source": []}, {"source": [1]}],
)
def test_invalid_slice_filter_type_is_rejected(invalid_filter: object) -> None:
    payload = _chunk_ground_truth()
    payload["evaluation_slices"] = [
        {"id": "invalid", "label": "Invalid", "filter": invalid_filter},
    ]

    with pytest.raises(ValueError, match="filter"):
        _canonicalize_ground_truth(payload)


def test_page_level_qrels_rejects_chunk_judgments() -> None:
    payload = {
        "metadata": {"ground_truth_type": "page_level_qrels"},
        "questions": [
            {
                "expected_answer_type": "found",
                "question": "Where is the answer?",
                "question_id": "q1",
                "relevant_chunks": [{"chunk_id": "chunk_1", "relevance": 3}],
                "relevant_pages": [{"page_index": 0, "pdf_sha1": "abc"}],
            }
        ],
    }

    with pytest.raises(ValueError, match="page_level_qrels questions cannot include relevant_chunks"):
        _canonicalize_ground_truth(payload)


def test_chunk_level_qrels_rejects_page_judgments() -> None:
    payload = _chunk_ground_truth()
    payload["questions"][0]["relevant_pages"] = [{"page_index": 0, "pdf_sha1": "abc"}]

    with pytest.raises(ValueError, match="chunk_level_qrels questions cannot include relevant_pages"):
        _canonicalize_ground_truth(payload)


def test_slice_filter_uses_or_within_field_and_and_between_fields() -> None:
    row = {
        "question_metadata": {
            "source": "erc2_original",
            "difficulty": "hard",
            "tags": ["numeric", "multi_page"],
        }
    }

    assert question_metadata_matches(row, {"source": ["other", "erc2_original"]})
    assert question_metadata_matches(row, {"source": ["erc2_original"], "difficulty": ["hard"]})
    assert not question_metadata_matches(row, {"source": ["erc2_original"], "difficulty": ["medium"]})
    assert question_metadata_matches(row, {"tags": ["semantic_mapping", "multi_page"]})
    assert not question_metadata_matches(row, {"tags": ["table_lookup"]})


def test_slice_metrics_use_matching_rows_and_shared_page_aggregation() -> None:
    rows = [
        {
            "status": "completed",
            "question_metadata": {"source": "original", "difficulty": "hard"},
            "metrics": {"page_hit_at_k": 1.0, "page_mrr_at_k": 0.5, "page_recall_at_k": 0.5},
        },
        {
            "status": "completed",
            "question_metadata": {"source": "synthetic", "difficulty": "easy"},
            "metrics": {"page_hit_at_k": 0.0, "page_mrr_at_k": 0.0, "page_recall_at_k": 0.0},
        },
    ]
    overall_before = aggregate_metrics(rows)

    slices = build_slice_metrics(
        rows,
        [
            {"id": "original", "label": "Original", "filter": {"source": ["original"]}},
            {"id": "empty", "label": "Empty", "filter": {"difficulty": ["missing"]}},
        ],
    )

    assert aggregate_metrics(rows) == overall_before == {
        "page_hit_at_k": 0.5,
        "page_mrr_at_k": 0.25,
        "page_recall_at_k": 0.25,
    }
    assert slices["original"]["question_count"] == 1
    assert slices["original"]["metric_averages"] == {
        "page_hit_at_k": 1.0,
        "page_mrr_at_k": 0.5,
        "page_recall_at_k": 0.5,
    }
    assert slices["empty"]["question_count"] == 0
    assert slices["empty"]["metric_averages"] == {}
    assert slices["empty"]["warnings"]


def test_chunk_level_slice_aggregation_keeps_chunk_metric_keys() -> None:
    rows = [
        {
            "status": "completed",
            "question_metadata": {"source": "a"},
            "metrics": {"hit_at_k": 1.0, "mrr_at_k": 0.5, "recall_at_k": 0.25},
        }
    ]

    result = build_slice_metrics(
        rows,
        [{"id": "a", "label": "A", "filter": {"source": ["a"]}}],
    )

    assert result["a"]["metric_averages"] == rows[0]["metrics"]


def test_wheeler_slice_counts_match_annotated_19_question_benchmark() -> None:
    hard = {"q000001", "q000002", "q000003"}
    medium = {"q000004", "q000007", "q000010", "q000012", "q000013", "q000016"}
    rows = []
    for index in range(1, 20):
        question_id = f"q{index:06d}"
        difficulty = "hard" if question_id in hard else "medium" if question_id in medium else "direct_lookup"
        rows.append(
            {
                "status": "completed",
                "question_metadata": {
                    "source": "erc2_original" if index <= 3 else "synthetic_chatgpt",
                    "difficulty": difficulty,
                },
                "metrics": {"page_recall_at_k": 1.0},
            }
        )
    definitions = [
        {"id": "erc2", "label": "ERC2 Original", "filter": {"source": ["erc2_original"]}},
        {"id": "synthetic", "label": "Synthetic", "filter": {"source": ["synthetic_chatgpt"]}},
        {"id": "hard", "label": "Hard", "filter": {"difficulty": ["hard"]}},
        {"id": "medium", "label": "Medium", "filter": {"difficulty": ["medium"]}},
        {"id": "direct", "label": "Direct lookup", "filter": {"difficulty": ["direct_lookup"]}},
    ]

    result = build_slice_metrics(rows, definitions)

    assert len(rows) == 19
    assert result["erc2"]["question_count"] == 3
    assert result["synthetic"]["question_count"] == 16
    assert result["hard"]["question_count"] == 3
    assert result["medium"]["question_count"] == 6
    assert result["direct"]["question_count"] == 10


def test_canonical_page_level_ground_truth_can_be_uploaded_again() -> None:
    payload = {
        "schema_version": "raglab.ground_truth.v1",
        "metadata": {"ground_truth_type": "page_level_qrels"},
        "questions": [
            {
                "expected_answer": 42,
                "expected_answer_type": "found",
                "metadata": {"source": "original"},
                "question": "What is the value?",
                "question_id": "q000001",
                "question_type": "number",
                "reasoning_process": "Read the statement.",
                "relevant_chunks": [],
                "relevant_pages": [{"page_index": 2, "pdf_sha1": "abc"}],
            }
        ],
    }

    canonical = _canonicalize_ground_truth(payload)

    assert canonical["questions"][0]["expected_answer"] == 42
    assert canonical["questions"][0]["reasoning_process"] == "Read the statement."
    assert canonical["questions"][0]["relevant_pages"] == [{"page_index": 2, "pdf_sha1": "abc"}]


def test_old_saved_experiment_payload_without_slice_metrics_is_accepted() -> None:
    payload = SavedExperimentCreate.model_validate(
        {
            "data_asset_id": "data-1",
            "name": "Old experiment",
            "params_hash": "sha256:old",
            "params_snapshot_json": {},
            "metrics_summary_json": {"metric_averages": {"recall_at_k": 0.5}},
        }
    )

    assert "slice_metrics" not in payload.metrics_summary_json


def test_authoring_pack_schema_allows_question_metadata() -> None:
    metadata_schema = _ground_truth_schema()["properties"]["metadata"]

    assert metadata_schema["additionalProperties"] is True
    assert metadata_schema["properties"]["tags"] == {
        "items": {"type": "string"},
        "type": "array",
    }
