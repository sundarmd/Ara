# Evaluation

Ara has a lightweight golden-question eval harness for checking retrieval behavior, citation presence, insufficient-context handling, and structured recommendation fields.

## Files

- `evals/golden_questions.yaml` contains the eval cases. It is YAML-compatible JSON so the runner can validate it with only the Python standard library.
- `evals/run_eval.py` posts each question to the local `/chat/stream` endpoint, parses SSE events, and checks the final answer payload.

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
