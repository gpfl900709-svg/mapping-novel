# mapping-novel

공개 안전 매핑 앱과 내부 운영 앱을 분리해, S2 지급정산 기준으로 플랫폼 정산서를 매핑하고 S2/IPS/admin/account 보조 조사를 운영하는 Streamlit + operator repo입니다.

## What This Does

- 공개 앱: 정산서 업로드 → 개인정보 없는 S2 제목/채널 기준 매핑
- 내부 앱: 검토필요/PD 작업지시 리포트 생성
- S2 기준, 누락 guard, 청구 guard, 판매채널콘텐츠 lookup 최신화
- IPS 콘텐츠 보조자료 최신화
- `ops/` 아래에 IPS/admin/account 운영 스크립트 보관

## Quick Start

```powershell
pip install -r requirements.txt
streamlit run app.py
```

기존 전체 운영 UI는 내부 전용 entrypoint로 실행합니다.

```powershell
streamlit run internal_app.py --server.address 127.0.0.1
```

운영용 live 작업까지 할 때:

```powershell
pip install -r requirements.txt -r ops\requirements-ops.txt
python -m playwright install chromium
Copy-Item "ops\SIAAN Project\.env.example" "ops\SIAAN Project\.env"
```

## Main Paths

```text
app.py                         공개 안전 Streamlit 앱
internal_app.py                내부 운영 전용 Streamlit 앱
public_mapping.py              공개 reference/result/export 보안 경계
batch_reports.py               복수 정산서/PD 작업지시 리포트
mapping_core.py                핵심 매핑 로직
cleaning_rules.py              제목 정제 규칙
matching_rules.py              S2 판매채널 필터
scripts/                       최신화/운영 CLI
data/                          앱이 읽는 기준 데이터
ops/                           IPS/admin/account live 운영 레이어
doc/OPERATIONS.md              상세 운영 설명
doc/2026-05-19/                최신 인수인계/감리 문서
```

## Daily Refresh

S2 기준은 사내망 PC에서 전체 교체 방식으로 최신화합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_daily_s2_refresh.ps1 -RepoRoot <repo-path> -Python <python.exe>
```

수동 실행:

```powershell
python scripts\refresh_kiss_payment_settlement.py --env-file .env --mode full-replace --lookup-only --page-size 50000 --content-style-code 102
python scripts\refresh_s2_reference_guards.py --env-file .env --page-size 1000000 --content-style-code 102
python scripts\refresh_s2_sales_channel_contents.py --env-file .env --content-style-code 102
python scripts\refresh_ips_auxiliary_data.py --env-file .env
```

## Generated ID Gap Triage

Google Sheet의 `S2_판매채널콘텐츠ID` 빈 행은 먼저 S2 기준에서 진짜 부재인지 확인합니다.

```powershell
python scripts\triage_generated_id_gaps.py
```

공개 CSV export가 막혀 있으면 시트를 CSV로 내려받아:

```powershell
python scripts\triage_generated_id_gaps.py --input <sheet.csv>
```

결과는 기본적으로 `doc/YYYY-MM-DD/generated_id_gap_triage.csv`에 저장됩니다.

판정 순서:

1. S2 지급정산 기준 exact match
2. S2 판매채널콘텐츠 lookup exact match
3. S2 정산정보누락/청구정산 guard
4. S2 타채널 지급정산 증거 확인
5. S2 fuzzy 후보
6. IPS/admin/account 조사

`S2_타채널지급정산_존재`는 판매채널 추가 확정이 아닙니다. 타채널 ID는 입력하지 않고, IPS 콘텐츠 상세의 정산정보에서 source 통합 계약 ID를 확인한 뒤 분기합니다.

- `source 통합 계약 ID`가 0이 아닌 단일 값이면 해당 계약 ID 기준으로 판매채널 추가를 진행할 수 있습니다.
- 정산정보가 전부 `0`이면 판매채널 추가가 아니라 계약/정산 연결 보강이 먼저입니다.
- 0이 아닌 계약 ID가 여러 개면 계약서를 사람이 선택한 뒤 진행합니다.

## Operator Layer

`ops/`는 포크 인수인계를 위해 SSOT/SIAANE 쪽 운영 코드를 흡수한 영역입니다.

- [ops/README.md](ops/README.md)
- [ops/INPUTS.md](ops/INPUTS.md)
- [ops 흡수 적대적 감리](doc/2026-05-19/ops_absorption_adversarial_audit.md)
- [운영 capability map](doc/2026-05-19/operator_handoff_capability_map.md)

live write 도구는 기본적으로 dry-run/preview 우선으로 보정되어 있습니다. 실제 write는 각 스크립트의 `--write` 또는 명시 옵션을 확인하고 소량으로만 실행합니다.

## Tests

```powershell
python -m unittest discover -s tests -v
python -m py_compile app.py internal_app.py public_mapping.py mapping_core.py matching_rules.py parallel_mapping.py
```

## Notes

- 실제 `.env`와 local 작업 산출물은 git에 올리지 않습니다.
- 공개/내부 배포 경계와 reference 갱신 절차는 [doc/PUBLIC_INTERNAL_BOUNDARY.md](doc/PUBLIC_INTERNAL_BOUNDARY.md)를 따릅니다.
- 상세 운영 히스토리는 [doc/OPERATIONS.md](doc/OPERATIONS.md)에 보존했습니다.
- 과거 조사/증거 파일은 아직 repo에 남아 있으나, 신규 운영자는 위 `Main Paths`와 `ops/` 문서를 우선 보면 됩니다.
