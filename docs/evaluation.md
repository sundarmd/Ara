# Evaluation

Ara has a lightweight golden-question eval harness for checking retrieval behavior, answer citation IDs against returned sources, insufficient-context handling, and structured recommendation fields.

## Files

- `evals/golden_questions.yaml` contains the eval cases. It is YAML-compatible JSON so the runner can validate it with only the Python standard library.
- `evals/run_eval.py` posts each question to the local `/chat/stream` endpoint, parses SSE events, and checks the final answer payload.

## Checks

The runner supports these lightweight expectations:

- `min_sources`: require at least this many returned sources.
- `answer_must_have_citations`: require the answer to contain at least one bracket citation, such as `[1]`, that matches a returned `sources[].citation_id`.
- `answer_must_include` / `answer_must_include_any`: require exact text markers in the answer.
- `insufficient_context`: require the answer to state that context is insufficient.
- `min_recommendations`: require at least this many structured recommendations.
- `required_recommendation_fields`: require each returned recommendation to include listed fields.

This is not a full semantic grounding evaluator. The citation check proves that the answer cites returned source IDs; it does not prove every sentence is supported by the cited source.

## Validate the Eval Set

```bash
python3 evals/run_eval.py --dry-run
```

## Run Against a Local Backend

Start the app with a populated document store, then run:

```bash
python3 evals/run_eval.py --api-url http://localhost:8000
```

If API-key auth is enabled:

```bash
python3 evals/run_eval.py --api-url http://localhost:8000 --api-key "$API_KEY"
```

The runner exits non-zero when any case fails and prints a JSON summary with per-case failures.
