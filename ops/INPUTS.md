# Operator Input Manifest

This folder contains code, not the historical operating data.

Use this manifest before handing the repo to another PC/operator. If an item is marked local, do not commit it unless a separate review says it is safe.

## Required Local Setup

```powershell
pip install -r requirements.txt -r ops\requirements-ops.txt
python -m playwright install chromium
Copy-Item "ops\SIAAN Project\.env.example" "ops\SIAAN Project\.env"
```

Fill `ops\SIAAN Project\.env` locally.

## Shared Local Inputs

These are expected by multiple scripts and are intentionally ignored when local.

```text
ops/SIAAN Project/config/work_cid_registry.local.csv
ops/SIAAN Project/config/manual_overrides.local.json
ops/SIAAN Project/config/cp_pen_aliases.local.json
ops/SIAAN Project/data/exports/barobook/
ops/SIAAN Project/data/catalog/
```

## Account / Crosswalk Rebuild Chain

Minimum inputs:

```text
ops/SIAANE_v2/index_f.xlsx
ops/SIAANE_v2/manager_author_manual_groups.json
ops/SIAAN Project/config/work_cid_registry.local.csv
ops/SIAAN Project/config/cp_pen_aliases.local.json
ops/SIAAN Project/data/exports/barobook/*_조원재_matched.xlsx
ops/SIAAN Project/data/exports/barobook/*__NAS_IPS_ACCOUNT_예금주_조원재_author_details.csv
```

Typical order:

```powershell
python ops\SIAANE_v2\build_manager_author_ssot.py --manager 조원재
python ops\SIAANE_v2\account\build_account_observation_bundle.py
python ops\SIAANE_v2\account\build_account_decision_queue.py
python ops\SIAANE_v2\account\build_account_rights_canonical.py
python ops\SIAANE_v2\crosswalk\build_account_ips_cid_seed.py
python ops\SIAANE_v2\crosswalk\build_account_ips_action_queue.py
```

Generated outputs are ignored:

```text
ops/SIAANE_v2/담당작가_ssot/
ops/SIAANE_v2/account/exports/
ops/SIAANE_v2/crosswalk/exports/
```

## IPS Sales Channel Flow

Read-only lookup first:

```powershell
python ops\scripts\ips_sales_channel_harness.py --input <sheet-or-csv> --env-file "ops\SIAAN Project\.env" --headless
```

Standalone adder is dry-run by default after absorption:

```powershell
python ops\scripts\ips_sales_channel_adder.py --input <harness-output.csv>
```

Live add requires explicit `--write`:

```powershell
python ops\scripts\ips_sales_channel_adder.py --input <harness-output.csv> --write --env-file "ops\SIAAN Project\.env"
```

One-shot pipeline is preview-only by default. Live IPS add/upload requires explicit `--write`;
`--dry-run` is accepted as an explicit preview flag.

## Dummy Contract / Admin Working Files

Several copied recipes expect local working CSV/XLS files under:

```text
ops/SIAANE_v2/담당자없는작품_재정리/
ops/SIAANE_v2/담당컨텐츠_분류/
```

Those folders are ignored because they contain job-specific evidence and live-operation outputs. Rebuild or copy them locally only for the specific case being worked.

## Included Artifact

```text
ops/더미+계약서.pdf
```

The dummy contract PDF is included because the KIPM dummy-contract scripts use it as their default attachment.

