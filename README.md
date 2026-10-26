# Streaming request creation retry validation

Product commit: `52e18284e3e1cf7312f72ebfeb969a2eadc811ce`  
Product tree: `e01413119210abdf190aab7eff963dc30772c83c`  
Base: `27631eb4e1a7da4736e9ba1c9f9e5a6b42b77c94`  
Package and tested wheel version: **2.8.2** (static pyproject version, unchanged by the commit).

The patch retries exceptions raised before a stream response exists. Creation and iteration share one retry iterator and budget across sync/async, context, and resume paths. This branch contains validation evidence only; product changes live on `fix/retry-initial-stream-creation`.

## Regression and full suites

The 40 added cases produce **32 failed / 8 passed** on the original implementation (the 8 non-retryable controls already pass), then all 40 pass with the fix. The complete retry suite is 211 tests. Each full Python 3.10–3.13 run reports **2685 passed, 5 skipped, 100.00% coverage**. All 1846 tracked Python source/data files were verified byte-for-byte against canonical Git blobs before each full suite. The matrix used VCR playback (`--vcr-record=none`) and disconnected container networking; no cassettes were recorded and no external inference was used.

Commands for a Linux checkout of the product commit, repeated for Python 3.10,3.11,3.12,3.13:

```sh
cd python
uv sync --all-extras --dev
uv run pytest --cov --cov-config=.coveragerc --cov-report=xml --cov-report=term-missing --vcr-record=none
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pyright .
uv run bash scripts/validate_extra_imports.sh
```

Ruff, format, lock, EXTRA_IMPORTS, codespell, actual root `bun run typecheck` (TypeScript/Python/website), and genuine Husky/lint-staged on the five Python files completed successfully. Pyright reports 0 errors and 5 MLX source-resolution warnings on this platform. Example generation produced 32 files that match the tracked index exactly. The exact CI datamodel-codegen command completed successfully; upstream's configured output directory is untracked, so this is not presented as a comparison against committed generated modules.

Root AGENTS mentions `bun run lint:oxlint` and `bun run test:coverage`; those names are absent from root package.json (the retained logs show the actual missing-script results). They belong to the individual JavaScript packages. For this patch (five Python files and a two-line documentation paragraph), the actual `.github/workflows/ci.yml` filters select Python quality/full coverage jobs and codespell; TypeScript and website lint/runtime coverage jobs are not selected. No claim is made that those unrun JavaScript suites passed. The full root typecheck did execute and pass.

## Installed-wheel HTTP/SSE proof

`runtime_http.py` uses the real public RetryModel and OpenAI SDK, with SDK retries disabled, against a synthetic loopback HTTP/SSE server. All 12 sync/async cases passed on an installed canonical-LF wheel: first 429/disconnect/timeout succeeds after 2 requests, exhaustion stops after 3 requests, and success/authentication failure sends 1 request. The canonical baseline surfaces first creation failures after 1 request. This is actual local transport/SDK validation, not a paid provider or model inference test.

```sh
cd python
uv build --wheel --out-dir /tmp/canonical-dist --offline
uv pip install --target /tmp/canonical-installed --no-deps --offline /tmp/canonical-dist/mirascope-2.8.2-py3-none-any.whl
uv run python /path/to/runtime_http.py --source /tmp/canonical-installed --expect fixed --output /tmp/runtime.json
```

The final wheel's 189 packaged source files match the tested Git index; its SHA256 and the three changed runtime module hashes are in `final-source-binding.json`. Test data/PDF fixtures use raw Git bytes. Earlier Windows-CRLF archive matrix attempts were superseded and are not included as passing evidence.

Only the explicit allowlist in `manifest.json` was published. Local account/workspace paths were replaced with placeholders; raw-source and published SHA256 values identify that sanitization. No unrelated project records, credentials, caches, archives, dependencies, or binaries are included. AI assistance was used for implementation and review; no claim of human execution or approval is made.

The full code tests ran on commit `acf18039c6c367e80538bc5b695858e81b87d425`. The final additional commit only restores the reliability documentation paragraph required by the current contributing guide; all 1846 Python tracked blobs and all 189 packaged wheel source files are unchanged. The MDX document compiles and codespell passes. Baseline and candidate have identical unrelated Oxfmt debt; the added paragraph is preserved by the formatter. The actual CI has no content/docs formatter job. See `docs-scope-final.json`.
