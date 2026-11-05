#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
unset PYTHONPATH UV_NO_SYNC
uv sync --frozen
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
uv build --out-dir "$scratch/identity"
uv build compatibility --out-dir "$scratch/bridge"
uv export --frozen --no-emit-project --format requirements-txt --output-file "$scratch/requirements.txt" >/dev/null
uv venv --python 3.13 "$scratch/venv"
uv pip sync --python "$scratch/venv/bin/python" "$scratch/requirements.txt"
uv pip install --python "$scratch/venv/bin/python" --no-deps "$scratch"/identity/*.whl "$scratch"/bridge/*.whl
cp -R compatibility/tests "$scratch/tests"
(cd "$scratch" && "$scratch/venv/bin/python" -I -m pytest -c /dev/null tests)
uv run --frozen python - "$scratch" <<'PY'
import pathlib, sys, tarfile
root = pathlib.Path(sys.argv[1])
with tarfile.open(next((root / 'bridge').glob('*.tar.gz'))) as archive:
    archive.extractall(root / 'sdist', filter='data')
PY
uv build --wheel "$scratch"/sdist/* --out-dir "$scratch/rebuilt"
uv pip install --python "$scratch/venv/bin/python" --no-deps --reinstall "$scratch"/rebuilt/*.whl
(cd "$scratch" && "$scratch/venv/bin/python" -I -m pytest -c /dev/null tests)
