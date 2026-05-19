from __future__ import annotations

from .kiss import KISS_SITE
from .kipm import KIPM_SITE


SITE_REGISTRY = {
    KIPM_SITE.name: KIPM_SITE,
    KISS_SITE.name: KISS_SITE,
}


def get_site(name: str):
    normalized = name.strip().lower()
    try:
        return SITE_REGISTRY[normalized]
    except KeyError as exc:
        raise KeyError(f"지원하지 않는 사이트입니다: {name}") from exc
