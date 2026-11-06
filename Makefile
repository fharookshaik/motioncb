SHELL := powershell.exe
.SHELLFLAGS := -NoLogo -NoProfile -NonInteractive -Command

.PHONY: setup labels splits audit-sample testsets test lint check disk

setup:
	uv sync --extra dev --extra geo --extra train --extra imagery

labels:
	uv run python -m solarde.labels.curate --config configs/data.yaml

splits:
	if ((Test-Path 'data/processed/splits_s1_blocks.gpkg') -and ((Test-Path 'runs/registry.csv') -or (Test-Path 'runs/test_access.log') -or (Get-ChildItem 'runs' -Directory -ErrorAction SilentlyContinue | Where-Object { $$_.Name -ne 'audit_m1_3' } | Select-Object -First 1))) { Write-Error 'Refusing: training runs exist and split s1 is frozen (CLAUDE.md invariant 1).'; exit 1 }; uv run python -m solarde.splits.blocks --config configs/splits.yaml --data-config configs/data.yaml

audit-sample:
	uv run python scripts/make_audit_sample.py --config configs/splits.yaml

testsets:
	uv run python -m solarde.splits.tnew --config configs/testsets.yaml
	uv run python -m solarde.labels.kit_indep --config configs/testsets.yaml

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

check: test lint disk

disk:
	foreach ($$path in @('data', 'runs')) { if (Test-Path $$path) { $$bytes = (Get-ChildItem $$path -Recurse -File -Force -ErrorAction Stop | Measure-Object -Property Length -Sum).Sum; '{0}: {1:N2} GB' -f $$path, ($$bytes / 1GB) } }; $$drive = Get-PSDrive -Name (Get-Location).Drive.Name; 'Free space: {0:N2} GB' -f ($$drive.Free / 1GB)
