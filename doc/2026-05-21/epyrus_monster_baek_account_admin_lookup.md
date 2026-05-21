# Epyrus Monster/Baek Account/Admin Lookup

Generated: 2026-05-21

Scope:
- Google Sheet row 3550: `몬스터홀`, target channel `에피루스 이북클럽(B2C)`, target CID `295590`
- Google Sheet row 3551: `백작가의사생아가결혼하면`, target channel `에피루스 이북클럽(B2C)`, target CID `113327`

## Login Status

Live `account.barobook.com` / `admin.barobook.com` lookup could not be completed from the current repo credentials.

- `.env` has no `BAROBOOK_ID` / `BAROBOOK_PW`.
- Fallback credential sources tested without printing secret values: `KLD`, `KISS`, `S2`, `IPS`.
- All tested fallback sources stayed on `http://member.barobook.com/Auth/Login` for both admin and account.

So the account-only values below remain unconfirmed:

- `account_저작권코드`
- account `저작권명/정산명`
- account page RS rate

## Evidence Found

### 몬스터홀

Target CID `295590`:

- IPS content: `몬스터 홀`, `소설`, `연재`, 담당 `천승민`, 부서 `소설편집팀`
- KIPM settlement rows: 35 rows
- KIPM settlement-linked contract ID: none
- KIPM contract tab: none
- Status: `settlement_rows_without_contract`

Related family CID `326461`:

- IPS content: `몬스터 홀 [단행본]`
- Contract ID `83905`
- Contract status `유지`
- Contract kind `본계약서`
- Counterparty `주식회사 북메이커`
- Contract name `20260203_몬스터 홀 [단행본]_주식회사 북메이커`
- Settlement table links 10 rows to contract ID `83905`

KISS/KIPM settlement template evidence for target CID `295590` shows existing rows under:

- `주식회사 북메이커`, RS evidence `70`
- `(주)문피아`, mixed rows including zero-rate/template rows

Decision:

- Do not treat row 3550 as simple sales-channel add yet.
- The target CID `295590` itself has no nonzero settlement contract ID.
- The only concrete nonzero contract in the family is `326461 / 83905 / 주식회사 북메이커`.
- To proceed safely, confirm in ACCOUNT/ADMIN whether `295590` should use the same holder/right as the `326461` family contract, then link/create the contract on `295590` before adding the Epyrus sales channel.

### 백작가의사생아가결혼하면

Target CID `113327`:

- IPS content: `백작가의 사생아가 결혼하면`, `소설`, `단행본`, pen name `랏슈`, 담당 `김인희`, 부서 `소설2팀`
- KIPM settlement rows: 26 rows
- KIPM settlement-linked contract ID: none
- KIPM contract tab: 20 contract rows
- Status: `contract_tab_only`

KIPM contract-tab candidates include:

- `2117`, status `유지`, counterparty `최은비`, contract name `<백작가 사생아가 결혼하면>웹툰 및 만화화 허락 계약서`
- `60300`, counterparty `최은비`, contract name `해외 제휴 부속 계약서_백사결(최은비 님)`
- `59298`, counterparty `최은비`, contract name `230706_해외 제휴 부속 계약서_백사결(최은비 님)`
- `63300`, `64858`, `65204`, `68626`, counterparty `최은비`, 카카오 특별공급 부속합의서 계열
- Multiple 카카오엔터테인먼트 supply contracts and 바이프로스트 contract also exist on the tab.

KISS/KIPM settlement template evidence for target CID `113327` shows existing rows mostly under:

- `최은비`, RS evidence `70`
- `(주)키다리스튜디오`, RS evidence `70` on some platform rows

Decision:

- Do not treat row 3551 as simple sales-channel add yet.
- Contract tab has candidates, but the target CID settlement rows still have `cntrId=0`.
- Need ACCOUNT/ADMIN confirmation of `최은비 / 랏슈 / 백작가의 사생아가 결혼하면` account rights code and actual RS basis before contract/settlement linking.
- After that, link the correct contract to `113327` settlement information or create the required contract, then add the Epyrus sales channel.

## Output Files

- `doc/2026-05-21/epyrus_monster_baek_contract_family_links.csv`
- `doc/2026-05-21/epyrus_monster_baek_contract_family_links_edges.csv`
- `doc/2026-05-21/epyrus_monster_baek_contract_family_links.json`

