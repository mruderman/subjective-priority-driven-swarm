#!/usr/bin/env bash
# Runs tests per category (unit/integration/e2e) using python3.11 and writes coverage XMLs
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY=python3.11
echo "Using interpreter: $($PY --version 2>&1)"

mkdir -p .coverage-artifacts htmlcov

echo "Running unit tests..."
$PY -m pytest tests/unit -q --maxfail=1 --disable-warnings \
  --cov=spds --cov-report=xml:coverage-unit.xml --cov-report=term || true

echo "Running integration tests..."
$PY -m pytest tests/integration -q --maxfail=1 --disable-warnings \
  --cov=spds --cov-report=xml:coverage-integration.xml --cov-report=term || true

echo "Running e2e tests..."
$PY -m pytest tests/e2e -q --maxfail=1 --disable-warnings \
  --cov=spds --cov-report=xml:coverage-e2e.xml --cov-report=term || true

echo "Running full suite to produce overall coverage html and xml..."
$PY -m pytest -q --maxfail=1 --disable-warnings \
  --cov=spds --cov-report=xml:coverage-all.xml --cov-report=html:htmlcov || true

echo "Artifacts: coverage-unit.xml, coverage-integration.xml, coverage-e2e.xml, coverage-all.xml, htmlcov/"

echo "Done"
