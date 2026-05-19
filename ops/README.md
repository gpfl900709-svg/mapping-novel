# Absorbed Operator Layer

This folder is a small, local mirror of the SSOT/SIAANE operator scripts needed when `mapping-novel` must do more than read S2/IPS data.

It is intentionally separated from the Streamlit app path. The app can run without this folder, while operator work can use this folder when live KIPM/admin/account actions are needed.

## Layout

```text
ops/
  scripts/
    ips/                         # shared KIPM/KISS auth + Playwright harness
    ips_sales_channel_harness.py # KIPM detail/sales-channel lookup helpers
    ips_sales_channel_adder.py   # KIPM sales-channel add helpers
    rename_ips_content_titles_api.py
    google_sheet_generated_id_uploader.py
    chrome_debug_session.py
    create_kipm_content_contract.py
    create_kipm_dummy_contract.py
  SIAAN Project/
    .env.example                 # copy to .env locally, never commit real credentials
    admin_login.py               # Barobook admin login helper
    account_login.py             # Barobook account login helper
  SIAANE_v2/
    build_manager_author_ssot.py # manager-author scope builder
    account/                     # account canonical/decision-queue scripts
    crosswalk/                   # account↔IPS action queue scripts
    *.py                         # admin/IPS live recipes copied from SIAANE_v2
  더미+계약서.pdf
  requirements-ops.txt
```

## Install

From the repo root:

```powershell
pip install -r requirements.txt -r ops\requirements-ops.txt
python -m playwright install chromium
```

Create local credentials:

```powershell
Copy-Item "ops\SIAAN Project\.env.example" "ops\SIAAN Project\.env"
notepad "ops\SIAAN Project\.env"
```

## What Works Here

The copied scripts preserve the original relative path convention:

- scripts in `ops/scripts` treat `ops/SIAAN Project` as their project root.
- scripts in `ops/SIAANE_v2` treat `ops` as the repo root and import helpers from `ops/scripts`.
- dummy contract scripts use `ops/더미+계약서.pdf` by default.

## First Safe Checks

Run read-only probes before any write:

```powershell
python ops\SIAANE_v2\ips_live_lookup.py --env-file "ops\SIAAN Project\.env" --query "무유지" --page-size 10 --fetch-all --headless
python ops\scripts\probe_ips_managers.py --env-file "ops\SIAAN Project\.env" --headless
```

## Write Safety

Do not run write scripts directly on a new machine until a dry-run/verification path has been reviewed.

Higher-risk scripts include:

```text
ops\SIAANE_v2\apply_*_live.py
ops\SIAANE_v2\create_natoya_missing_cids_api.py  # preview by default; --write required
ops\scripts\create_kipm_content_contract.py
ops\scripts\create_kipm_dummy_contract.py
ops\scripts\ips_sales_channel_adder.py  # dry-run by default; --write required
```

Expected workflow:

1. Build or inspect a queue.
2. Run dry-run or lookup only.
3. Review the generated CSV/JSON.
4. Run write with a small explicit subset.
5. Verify by live lookup.

## Current Limitation

This is a code absorption, not a full data migration. Historical `raw/`, `stage/`, `canonical/`, and `exports/` files from `SIAANE_v2` are intentionally not copied. Rebuild or supply those inputs as needed.

See `ops/INPUTS.md` for the local input manifest and rebuild order.
