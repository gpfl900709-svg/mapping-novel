# Public / Internal Streamlit Boundary

## Entrypoints

- `app.py`: anonymous/public-safe mapping only.
- `internal_app.py`: existing full operator UI. Run only on a trusted workstation or authenticated internal deployment.

The public entrypoint must not import Notion, GitHub write, S2 authentication/refresh, guard, or payment-settlement modules. It reads only `data/public_s2_mapping_reference.csv`, which has the exact schema below:

```text
콘텐츠명
판매채널콘텐츠ID
콘텐츠ID
판매채널명
```

## Refresh

After the internal S2 lookup is refreshed, rebuild and validate the public projection:

```powershell
py -3.12 scripts\build_public_mapping_reference.py
py -3.12 scripts\build_public_mapping_reference.py --check
```

The builder fails if the reference schema drifts or an email / phone pattern is present.

## Runtime

Public:

```powershell
streamlit run app.py --server.address 127.0.0.1
```

Internal:

```powershell
streamlit run internal_app.py --server.address 127.0.0.1
```

For an anonymous cloud deployment, publish a dedicated bundle/repository containing only the public entrypoint, its read-only dependencies, and the sanitized reference. Do not deploy `internal_app.py`, `.env`, guard datasets, operational outputs, or connector secrets in that artifact.

Build and validate that minimal artifact with:

```powershell
py -3.12 scripts\build_public_deploy_bundle.py
```

The output is written below `.codex_tmp/public_deploy_bundle` and must be published to a separate public deployment repository. The builder uses an exact file allowlist and fails if an internal module is present.

## Security Contract

- Public exports use an exact output allowlist.
- Public XLSX and ZIP payloads are reopened and inspected before download.
- Uploaded originals are processed in memory and are never attached to Notion/GitHub.
- PD work orders, internal guards, candidate lists, contract/settlement metadata, assignee, and department data remain internal-only.
- Removing assignee and department data must not change match status or selected S2 IDs.
