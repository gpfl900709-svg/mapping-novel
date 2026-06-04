# KIPM/IPS/S2/Sheet Harness Global Safety Audit

Date: 2026-06-04 KST  
Scope: `ops/scripts`, `scripts/ips_safe_channel_backfill.py`, SIAANE v2 live/approval helpers, current 2026-06-04 investigation artifacts, and the Google Sheet/S2 sales-channel flow.

## Executive Summary

Confidence: 95%.

The immediate failure class is confirmed: a sales-channel name is not a stable key. `밀리의 서재` exists as at least two KIPM channel rows with different `schnId`/`cprCd`, and the working S2/external collection path expects `schnId=1106`, not the name-only first match `1359`.

The most important global improvement is now implemented for the current sales-channel pipeline:

- `ips_sales_channel_adder.py` selects channels with company context (`cprCd`) and refuses ambiguous duplicate-name rows when company context is absent.
- Post-write verification now checks the selected `schnId` as well as platform name and contract.
- Failed add/review statuses no longer masquerade as `sales_channel_content_id` values.
- `google_sheet_generated_id_uploader.py` only accepts positive numeric IDs for `paste_sales_channel_content_id`.
- `ips_sales_channel_pipeline.py` is preview-only by default; live add/upload requires explicit `--write`.

The remaining systemic risk is shared orchestration metadata: individual scripts have local guards, but there is no single shared write-run manifest and no universal post-write S2/ext-sale validation gate.

## Evidence Reviewed

Code and docs:

- `ops/README.md`: operating stance already says lookup/dry-run before writes and small explicit subsets for live writes.
- `ops/INPUTS.md`: standalone sales-channel adder is dry-run by default; live add requires `--write`; one-shot pipeline is preview-only by default and live add/upload requires `--write`.
- `ops/scripts/ips/core/harness.py`: shared KIPM/KISS login and artifact capture, but no write-run gate or manifest at the core harness layer.
- `ops/scripts/ips_sales_channel_harness.py`: read-only title/CID/platform lookup.
- `ops/scripts/ips_sales_channel_adder.py`: live sales-channel add path.
- `ops/scripts/ips_sales_channel_pipeline.py`: one-shot lookup -> add -> sheet upload orchestration.
- `ops/scripts/google_sheet_generated_id_uploader.py`: Google Sheet E-column writer.
- `ops/scripts/create_kipm_dummy_contract.py`: live dummy contract creator with account RS guard.
- `ops/scripts/create_kipm_content_contract.py`, `ops/scripts/rename_ips_content_titles_api.py`, SIAANE v2 live rename/create helpers.
- `scripts/ips_safe_channel_backfill.py`: older staged safe-channel backfill workflow.

Live/audit artifacts:

- `ops/SIAAN Project/output/investigate_account/20260604_kipm_milly_channel_list_probe.json`
- `ops/SIAAN Project/output/investigate_account/20260604_ext_sale_colct_milly_1106_1359_probe.json`
- `ops/SIAAN Project/output/investigate_account/20260604_milly_before_recreate_template_full.json`
- `ops/SIAAN Project/output/investigate_account/20260604_milly_recreate_1106_write_result.json`
- `ops/SIAAN Project/output/investigate_account/20260604_milly_recreate_1106_s2_ext_verify.json`
- `ops/SIAAN Project/output/investigate_account/20260604_s2_channel_duplicate_cpr_audit.json`
- `ops/SIAAN Project/output/investigate_account/20260604_kipm_channel_duplicate_cpr_audit.json`

## Confirmed Incident Class

Root cause:

1. KIPM sales-channel lookup can return multiple rows with the same visible name.
2. The previous automation could pick by name only.
3. For `밀리의 서재`, that selected `schnId=1359/cprCd=2000`.
4. S2/external collection expects the novel sales channel as `schnId=1106/cprCd=1000`.
5. A generated sales-channel content ID can exist in KIPM and still fail the downstream collection/search path if the wrong channel identity was used.

Confirmed repairs in live artifacts:

- `골 때리는 엄마들_미도파_1005083_949_확정`, CID `109322`, contract `86197`: corrected Milly row `schnCtnsId=906884`, `schnId=1106`.
- `슈퍼스타, 누구도 막을 수 없어_구라천재_1003257_471_확정`, CID `110469`, contract `86203`: corrected Milly row `schnCtnsId=906885`, `schnId=1106`.

## Current Guard Status

Implemented:

- Channel selection now uses `cprCd` when available and stops on duplicate company-code splits without enough context.
- Existing-platform detection no longer treats a same-name/wrong-channel row as safe.
- Post-write lookup requires the selected `schnId`; wrong-channel rows are rejected.
- `source_payment_setup_id` and `source_platform` can be passed as explicit template selectors for contract-ID-zero cases.
- Multiple contract-ID-zero payment setup rows are not auto-selected; the operator must provide `source_payment_setup_id` or `source_platform`.
- RS payload fields are opt-in except when setup passthrough needs them.
- Unresolved add statuses now route to `addition_review_note`, `check_source_contract_id`, or `manual_review`; they no longer fill `sales_channel_content_id`.
- Sheet uploader rejects non-positive and non-numeric values for `paste_sales_channel_content_id`.
- Sheet UI write path remains blocked by default unless `--allow-dangerous-ui-write` is explicitly passed.
- The deprecated `jo_blank_generated_id` pipeline preset keeps its legacy D-column and `조원재` manager filter instead of silently widening into the current E-column sheet preset.
- One-shot pipeline live mutation is gated by `--write`; default execution only builds lookup/addition artifacts.

Still missing:

- A shared write-run manifest across KIPM/IPS/S2/Sheet operations.
- A central status enum that every harness, adder, pipeline, and uploader must honor.
- A mandatory S2/ext-sale validation gate before a generated ID is allowed into Google Sheet E.
- A preflight drift check that fails fast when KIPM/S2 channel catalogs contain same-name rows split across different company/content families.

## Findings

P0 - Channel identity must be `name + schnId + company/content family`, not name only.

Evidence: `밀리의 서재` has duplicate visible-name rows in KIPM; corrected downstream rows validate with `schnId=1106`.  
Status: mitigated in `ips_sales_channel_adder.py`; not yet centralized for all future scripts.

P0 - Generated ID must not be sheet-uploadable until it is numeric and verified.

Evidence: previous unresolved-status handling could set `sales_channel_content_id` to review text and mark `next_action=paste_sales_channel_content_id`.  
Status: fixed for the adder/uploader path. Still needs a cross-script contract so future writers cannot reintroduce it.

P1 - One-shot pipeline write mode is too easy to trigger.

Evidence: previous code executed `process_rows(... write=True)` when `--dry-run` was absent and add candidates existed.  
Status: fixed. `ips_sales_channel_pipeline.py` now requires `--write` for live add/upload and rejects `--write --dry-run` as ambiguous.

P1 - Post-write verification is local, not global.

Evidence: adder verifies KIPM detail after write; sheet uploader verifies CSV export after write; external collection validation exists only in ad hoc investigation artifacts.  
Recommendation: promote ext-sale/S2 validation into a required reusable verifier before `next_action=paste_sales_channel_content_id`.

P1 - Contract-ID-zero cases require explicit source template identity.

Evidence: old logic assumed unified contract ID was enough; current production reality includes `pymtSetlSetmId` rows where `cntrId=0`.  
Status: adder now accepts `source_payment_setup_id` and `source_platform`; documentation/work queues should require one of `source_contract_id`, `source_payment_setup_id`, or representative contract decision evidence.

P1 - Account RS guards are good, but isolated.

Evidence: `create_kipm_dummy_contract.py` requires `account-rights-code`, `account-rights-name`, and matching `account-rs-rate`/`rs-rate`; tests cover the guard.  
Recommendation: keep this as the standard. Do not create new contract creators that infer RS from grade/defaults.

P2 - Legacy SIAANE v2 approval scripts need a label.

Evidence: several account/crosswalk scripts mutate local CSV/XLSX review queues without `--write`, while live remote writes generally do use `--write`.  
Recommendation: classify these as local-state mutators and add `--dry-run`/backup manifests if they are used again.

## Required Operating Contract

Before live KIPM/IPS/S2/Sheet mutation:

1. Build a candidate file.
2. Run read-only lookup.
3. Run drift preflight:
   - duplicate visible channel name,
   - different `schnId`,
   - different `cprCd`,
   - novel/video/admin/account family mismatch.
4. Resolve each mutation row to one explicit identity:
   - `ctnsId`,
   - platform display name,
   - expected `schnId`,
   - source `cntrId` or `pymtSetlSetmId`,
   - source platform/template row,
   - manager/owner if applicable.
5. Execute small live write batch only after explicit operator approval.
6. Verify KIPM detail.
7. Verify S2/ext-sale visibility with the expected `schnId`.
8. Only then mark `next_action=paste_sales_channel_content_id`.
9. Sheet writer accepts only positive numeric IDs and verifies export after write.

Stop rules:

- Same platform name appears under multiple `schnId` and expected channel ID is not known.
- Source has multiple unified contract IDs and no explicit source contract is provided.
- `cntrId=0` and no `pymtSetlSetmId` or representative decision evidence exists.
- Generated ID is not visible in S2/ext-sale under the expected `schnId`.
- Google Sheet target cell is not a single-cell reference.
- Any row belongs to a non-target manager/owner unless explicitly approved.

## Implementation Backlog

1. Add `ops/scripts/ips_safety_contract.py` with shared status constants, numeric ID validators, channel identity model, and write manifest helpers.
2. Add a reusable S2/ext-sale verifier that outputs `verification_status=passed|failed|blocked`.
3. Teach `google_sheet_generated_id_uploader.py` to require `verification_status=passed` for sales-channel ID uploads once the verifier exists.
4. Add a `channel_catalog_drift_check.py` preflight using KIPM/S2 channel catalogs; fail on same-name/different-family rows unless expected `schnId` is present.
5. Add per-run manifest:
   - input path and hash,
   - operator,
   - run timestamp,
   - live/dry-run mode,
   - before/after row snapshots,
   - verification artifacts,
   - rollback/manual cleanup notes.
6. Add a local-state mutator label and backups to SIAANE v2 account/crosswalk approval scripts.

## Receipt

Code changed in this audit:

- `ops/scripts/ips_sales_channel_adder.py`
- `ops/scripts/google_sheet_generated_id_uploader.py`
- `ops/scripts/ips_sales_channel_pipeline.py`
- `ops/INPUTS.md`
- `tests/test_ips_sales_channel_adder.py`
- `tests/test_google_sheet_generated_id_uploader.py`
- `tests/test_ips_sales_channel_pipeline.py`

Verification run:

- `python -m pytest tests/test_ips_sales_channel_adder.py tests/test_google_sheet_generated_id_uploader.py tests/test_ips_sales_channel_pipeline.py`
- Result: 33 passed.

Known limitation:

Network access was not used during final documentation after the OOM recovery. The live-state basis is the current repo plus saved 2026-06-04 investigation artifacts.
