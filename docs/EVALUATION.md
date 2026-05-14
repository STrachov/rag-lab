# Evaluation

## Purpose

Evaluation turns RAG development into an engineering process.

## Eval question format

```json
{
  "question_id": "q_001",
  "question": "What are the payment terms?",
  "answer_type": "factual",
  "expected_sources": [
    {
      "source_name": "contract.pdf",
      "page": 4,
      "section": "Payment Terms"
    }
  ],
  "expected_facts": [
    "Payment is due within 30 days"
  ]
}
```

## Answer types

```text
factual
multi_hop
comparison
definition
table_lookup
negative_not_found
summary
policy_interpretation
```

## Required retrieval metrics

```text
hit@k
MRR
source_recall
source_precision
```

## Required answer metrics

```text
answer_correctness
groundedness
citation_precision
citation_recall
not_found_accuracy
```

## Operational metrics

Always record:

```text
latency_ms
model
embedding_model
sparse_model
index_mode
retrieval_mode
reranker_model
candidate_k
prompt_tokens
completion_tokens
estimated_cost
```

## Failure categories

```text
source_not_retrieved
wrong_source_retrieved
correct_source_low_rank
answer_unsupported
answer_incomplete
citation_wrong
not_found_failed
table_parsing_failed
chunk_boundary_problem
metadata_filter_problem
```
