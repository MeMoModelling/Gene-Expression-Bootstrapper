---
name: maintain-gene-expression-bootstrapper
description: Maintain, test, debug, and deploy the Gene Expression Bootstrapper FastAPI/Docker application. Use when changing its Python backend, static frontend, Excel or CSV input handling, gene parsing and mapping behavior, bootstrap output, Docker image, dependencies, or Hugging Face Space deployment.
---

# Maintain Gene Expression Bootstrapper

Work from the repository root. Preserve the public upload, progress-stream, and ZIP-download workflow.

## Understand the application

- `backend/main.py`: FastAPI endpoints, background jobs, progress events, ZIP downloads, and static frontend mount.
- `utils/bootstrap_genes.py`: model gene parsing, identifier mapping, bootstrapping, and CSV generation.
- `utils/utils.py`: Excel model and mapping readers.
- `frontend/index.html`: upload interface and API client.
- `frontend/sample_*`: end-to-end test fixtures.
- `Dockerfile`: Hugging Face Docker Space entry point on port 7860.

## Make changes safely

1. Inspect the relevant source and sample file schemas before editing.
2. Keep model files, mapping files, and species prefixes in matching order.
3. Accept both stringified gene lists and Boolean expressions such as `gene_001 or gene_002`.
4. Apply `model_tag -> gene_id` mappings before filtering the expression table.
5. Retain genes without mappings so they can be bootstrapped.
6. Avoid loading entire large uploads into extra copies when changing processing code.
7. Preserve FastAPI field names used by the frontend:
   - `model_files`
   - `mapping_files`
   - `expr_file`
   - `batch_count`

## Validate

Run a small sample job before committing:

```bash
PYTHONPATH=. python3 -c "from utils.bootstrap_genes import bootstrap_genes; bootstrap_genes(['frontend/sample_model.xlsx'], ['frontend/sample_mapping.xlsx'], ['sample'], 'frontend/sample_combined_geneExpr.csv', '/tmp/gene-expression-bootstrapper-test', 3)"
```

Confirm:

- Three CSV files are created.
- Output contains mapped rows `NCBI_001` and `NCBI_002`.
- The unmapped `gene_003` row is bootstrapped.
- Placeholder rows such as `Spontaneous`, `Exchange`, and `Sink` are present.
- `git diff --check` passes.

For API changes, start the app in Docker or with Uvicorn and test `/api/process`, `/api/progress/{job_id}`, and `/api/download/{job_id}`.

## Deploy

The Hugging Face Space uses the repository's `main` branch and rebuilds after a push. After deployment:

1. Check that the runtime reaches `RUNNING`.
2. Submit the bundled sample files with a batch count of 3.
3. Wait for a `done` progress event.
4. Download the ZIP and inspect one CSV.
5. Distinguish Hugging Face scheduling failures from application exceptions. A message such as `Scheduling failure: unable to schedule` occurs before application code runs.

Never expose access tokens in code, logs, commits, or chat.

