# Novel Unsettled Processing Summary

Generated: 2026-05-21

Scope:

- Google Sheet rows after 3500 explicitly marked as `소설사업부(미정산)`.
- Target rows processed in this pass: 3501, 3529, 3537, 3538.

## Counterparty Basis

IPS/KIPM contract registration search returned two `소설사업부(미정산)`-named rows:

- `F000001002 / 기타-소설사업부(미정산) / 해외(사업자) / 9999999999`
- `Z000001417 / 기타-소설사업부(미정산) / 기타`

KIPM's normal selection path requires a usable business-number value for the counterparty row, so the selectable basis used for live registration was `F000001002`.

## RS Basis

The intended business handling is `RS 0%` for unsettled works.

KIPM's individual RS grid validation rejects numeric `0` in the normal `RS - 개별` path. The script therefore uses `RS정산방법=해당없음` when `--allow-zero-rs` is supplied. This keeps the live write on the normal KIPM save path while representing the unsettled/zero-settlement basis.

## Live Results

| Sheet row | CID | Title | Channel | Contract ID | Sales channel content ID | Payment settlement IDs |
| --- | ---: | --- | --- | ---: | ---: | --- |
| 3501 | 160166 | `[정산정보없음]_무유지` | 원스토어(소설) | 86041 | 488201 | 1085574; 1085565 |
| 3529 | 113774 | 상처 | 리디북스(소설) | 86042 | 904703 | 1085571; 1085566 |
| 3537 | 113098 | 무성격자 | 리디북스(소설) | 86043 | 113715 | 1085575; 1085567 |
| 3538 | 111932 | 나비를 잡는 아버지 | 리디북스(소설) | 86046 | 112512 | 1085576; 1085570 |

Google Sheet writeback:

- Target column: `E` (`S2_판매채널콘텐츠ID`)
- Cells updated: `E3501=488201`, `E3529=904703`, `E3537=113715`, `E3538=112512`
- Verification: 4/4 matched after CSV re-download.

## Evidence Files

- `doc/2026-05-21/novel_unsettled_contract_verify_4_final_edges.csv`
- `doc/2026-05-21/novel_unsettled_sales_channel_addition_write_audit.csv`
- `doc/2026-05-21/novel_unsettled_existing_platform_settlement_retry_audit.csv`
- `doc/2026-05-21/novel_unsettled_google_sheet_upload_live.json`
