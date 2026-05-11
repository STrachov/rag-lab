# Prompting

## Purpose

Prompt templates are part of experiment configuration and must be versioned.

## Location

```text
configs/prompts/
```

Examples:

```text
grounded_answer_v1.md
grounded_answer_v2.md
not_found_strict_v1.md
```

## Common variables

```text
{{question}}
{{context_chunks}}
{{citation_instructions}}
{{not_found_policy}}
{{answer_format}}
```

## Grounded answer rules

The prompt should instruct the model to:

1. Use only provided context.
2. Cite factual claims.
3. Say when evidence is insufficient.
4. Avoid guessing.
5. Preserve numbers, dates, names, and conditions exactly.

## Traceability

Every answer trace must record:

```text
prompt_template_id
prompt_hash
model
temperature
max_tokens
selected_chunk_ids
answer
citations
```

## Versioning rule

Do not edit important prompt templates in place. Create a new version:

```text
grounded_answer_v2.md
grounded_answer_v3.md
```
