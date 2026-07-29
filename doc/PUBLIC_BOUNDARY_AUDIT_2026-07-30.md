# Public Mapping Boundary Audit — 2026-07-30

## Conclusion

The working tree separates the anonymous mapping surface from the internal operator surface without changing the established title-matching result.

- GitHub repository visibility at review time: `PRIVATE`
- Critical/P0 findings in the final working tree: none found
- Public reference: 319,257 rows, exact four-column allowlist
- Email/phone-pattern hits in the public reference: 0
- Public deployment bundle: exact eight-file allowlist
- Full test suite: 230 total, 213 passed, 17 skipped because optional NAS fixtures were unavailable

This review covers the local working tree. It does not publish, commit, push, redeploy, wake, or disable the existing Streamlit Cloud application.

## Boundary

| Surface | Entrypoint | Contract |
| --- | --- | --- |
| Anonymous/public | `app.py` | Title and sales-channel mapping only |
| Trusted/internal | `internal_app.py` | Existing operator UI, connectors, guards, and work-order flows |

The internal entrypoint is the previous `app.py` plus an internal-only warning comment. Public deployment is built separately under `.codex_tmp/public_deploy_bundle`.

## Public Data Contract

The tracked public reference contains only:

1. `콘텐츠명`
2. `판매채널콘텐츠ID`
3. `콘텐츠ID`
4. `판매채널명`

Assignee, department, contact, contract, settlement, candidate-list, and operational columns are not included. Public mapping passes only `상품명` into the matching feed and exports an exact nine-column result allowlist.

## Findings Closed During Review

- Excel formula injection: formula-prefixed strings are neutralized and exported workbooks are reopened with formulas visible and rejected if any remain.
- XLSX expansion abuse: member count, member size, total expanded size, encryption, workbook structure, and suspicious compression ratio are checked before parsing.
- Aggregate work bypass: compressed upload bytes and mapping rows are capped before expensive mapping/export; processing stops when the run budget is exhausted.
- Stale result reuse: session signatures now include SHA-256 of each uploaded file's contents.
- Phone values hidden in ID columns: public identifiers must be numeric and phone-shaped numeric values are rejected.
- Destructive bundle output: output is restricted to a dedicated child under `.codex_tmp`.
- Internal report dependency in public bundle: the import is lazy and `work_order_reports.py` is absent from the public artifact.

## Verification Receipts

- `py -3.12 -m unittest discover -s tests`: 230 total, 213 passed, 17 skipped
- `py -3.12 -m py_compile ...`: passed
- `py -3.12 scripts/build_public_mapping_reference.py --check`: 319,257 rows, exact schema
- `py -3.12 scripts/build_public_deploy_bundle.py`: eight files, exact allowlist
- Streamlit health: local public, internal, and built-bundle servers all returned healthy
- Streamlit AppTest: public source and built bundle rendered with zero errors/exceptions
- Match invariance test: removing assignee/department preserves match status and selected S2 IDs
- `git diff --check`: passed

## Deployment Note

Changing the GitHub repository to private does not by itself prove that an already configured Streamlit Cloud application is disabled. The existing cloud deployment was not changed in this work. Publish the sanitized bundle to a deliberately selected deployment target, or explicitly disable the old application, as a separate approved action.
