# Epyrus Monster/Baek Account/Admin Lookup

Generated: 2026-05-21

Scope:
- Google Sheet row 3550: `몬스터홀`, target channel `에피루스 이북클럽(B2C)`, target CID `295590`
- Google Sheet row 3551: `백작가의사생아가결혼하면`, target channel `에피루스 이북클럽(B2C)`, target CID `113327`

## Login Status

Live `account.barobook.com` / `admin.barobook.com` lookup completed successfully with the SSOT env file:

- Env source: `C:\Users\wjjo\Desktop\업무자동화_ssot\SIAAN Project\.env`
- Account session check: `http://account.barobook.com/CpMgr/List` returned non-login page.
- Admin session check: admin Barobook cookies were issued and product additional-info endpoints returned copyright rows.

Important ID namespace note:

- KIPM/IPS target CIDs are not safe to reuse directly as Barobook admin product numbers.
- Direct admin lookups for `295590`, `326461`, `113327`, `113328` returned unrelated legacy Barobook products.
- Therefore the ACCOUNT mapping product numbers below are the reliable admin lookup keys, not the KIPM target CIDs.

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

ACCOUNT/ADMIN live evidence:

- ACCOUNT CP search found `4476942 / 최상진 ( 킹메이커 )`.
- CP `4476942` rights code `1005413`, rights name `기본정산율`, rates `B2C 70.00 / B2BC 70.00 / B2B 70.00`.
- ACCOUNT title search under rights `1005413` maps `[연재] 몬스터 홀` products, including `932251 / [연재] 몬스터 홀 100화 완결`; total title-hit sample count was 110.
- ADMIN product sample `932251` returned `최상진 - 기본정산율 : 자체 70.00%, 제휴 70.00%, B2B 70.00%`.
- ACCOUNT CP `4242646 / (주)문피아` also maps old one-volume products `316767`-`316774` for `몬스터 홀`, with admin rates `자체 70.00%, 제휴 65.00%, B2B 0.00%`.

Decision:

- Do not treat row 3550 as simple sales-channel add.
- The target CID `295590` itself has no nonzero settlement contract ID.
- The only concrete nonzero contract in the family is `326461 / 83905 / 주식회사 북메이커`.
- ACCOUNT/ADMIN confirms actual Barobook rights for the live `몬스터 홀` serial under `최상진(킹메이커) / 1005413`, but KIPM target settlement rows are still all `cntrId=0`.
- Proceed by selecting/linking a valid nonzero KIPM contract for target CID `295590`, or creating the required contract if no applicable contract can be linked, before adding the Epyrus sales channel.

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

ACCOUNT/ADMIN live evidence:

- ACCOUNT CP search found `4476606 / 최은비 ( 랏슈 )`.
- CP `4476606` rights code `1004835`, rights name `백작가의 사생아가 결혼하면`, rates `B2C 60.00 / B2BC 70.00 / B2B 70.00`.
- Rights `1004835` maps ordinary/non-Kakao products including `856320 / 백작가의 사생아가 결혼하면 1권`, `856316 / 백작가의 사생아가 결혼하면 세트`, `872880 / [봄툰] 백작가의 사생아가 결혼하면 1화 완결`.
- ADMIN samples `856320`, `856316`, `872880` returned `최은비 - 백작가의 사생아가 결혼하면 : 자체 60.00%, 제휴 70.00%, B2B 70.00%`.
- CP `4476606` also has rights `1004621 / [카카오] 백작가의 사생아가 결혼하면` with the same `60/70/70` rates and rights `1004910 / [원작] 백작가의 사생아가 결혼하면` with `5/5/5` rates.

Decision:

- Do not treat row 3551 as simple sales-channel add.
- Contract tab has candidates, but the target CID settlement rows still have `cntrId=0`.
- ACCOUNT/ADMIN confirms the normal B2C/ebook basis as `최은비(랏슈) / 1004835 / 백작가의 사생아가 결혼하면 / 60-70-70`.
- Next step is to select/link the correct nonzero KIPM contract from the existing target contract tab, or create the required contract if none of those contracts applies, before adding the Epyrus sales channel.

## Output Files

- `doc/2026-05-21/epyrus_monster_baek_contract_family_links.csv`
- `doc/2026-05-21/epyrus_monster_baek_contract_family_links_edges.csv`
- `doc/2026-05-21/epyrus_monster_baek_contract_family_links.json`
- `doc/2026-05-21/epyrus_monster_baek_account_admin_live_lookup.csv`
