from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any, Mapping


DIRECT_REFRESH_ENABLED_KEYS = ("S2_DIRECT_REFRESH_ENABLED", "S2_REFRESH_DIRECT_ENABLED")
DIRECT_REFRESH_TOKEN_KEYS = (
    "S2_DIRECT_REFRESH_TOKEN",
    "S2_DIRECT_REFRESH_ADMIN_TOKEN",
    "S2_ADMIN_REFRESH_TOKEN",
)
DIRECT_REFRESH_REQUIRE_TOKEN_KEYS = (
    "S2_DIRECT_REFRESH_REQUIRE_TOKEN",
    "S2_REFRESH_DIRECT_REQUIRE_TOKEN",
)
DIRECT_REFRESH_SECRET_SECTIONS = ("s2_refresh", "S2_REFRESH", "admin_refresh")


@dataclass(frozen=True)
class S2DirectRefreshConfig:
    enabled: bool = False
    admin_token: str = ""
    require_token: bool = True

    @property
    def token_ready(self) -> bool:
        return bool(not self.require_token or self.admin_token)

    @property
    def is_ready(self) -> bool:
        return bool(self.enabled and self.token_ready)

    def is_authorized(self, provided_token: object = "") -> bool:
        if not self.enabled:
            return False
        if not self.require_token:
            return True
        provided = _text(provided_token)
        return bool(self.admin_token and provided and hmac.compare_digest(self.admin_token, provided))


def build_s2_direct_refresh_config(values: Mapping[str, Any]) -> S2DirectRefreshConfig:
    return S2DirectRefreshConfig(
        enabled=_parse_bool(_first_value(values, DIRECT_REFRESH_ENABLED_KEYS), default=False),
        admin_token=_first_value(values, DIRECT_REFRESH_TOKEN_KEYS),
        require_token=_parse_bool(_first_value(values, DIRECT_REFRESH_REQUIRE_TOKEN_KEYS), default=True),
    )


def normalize_s2_direct_refresh_secret_values(raw_secrets: object) -> dict[str, str]:
    values: dict[str, str] = {}
    _copy_exact_keys(values, raw_secrets, DIRECT_REFRESH_ENABLED_KEYS + DIRECT_REFRESH_TOKEN_KEYS + DIRECT_REFRESH_REQUIRE_TOKEN_KEYS)
    for section_name in DIRECT_REFRESH_SECRET_SECTIONS:
        section = _mapping_value(raw_secrets, section_name)
        if section is None:
            continue
        _copy_exact_keys(
            values,
            section,
            DIRECT_REFRESH_ENABLED_KEYS + DIRECT_REFRESH_TOKEN_KEYS + DIRECT_REFRESH_REQUIRE_TOKEN_KEYS,
        )
        _copy_alias(values, "S2_DIRECT_REFRESH_ENABLED", section, ("enabled", "direct_enabled"))
        _copy_alias(values, "S2_DIRECT_REFRESH_TOKEN", section, ("admin_token", "direct_token"))
        _copy_alias(values, "S2_DIRECT_REFRESH_REQUIRE_TOKEN", section, ("require_token",))
    return values


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _first_value(values: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _text(values.get(key))
        if value:
            return value
    return ""


def _parse_bool(value: object, *, default: bool) -> bool:
    raw = _text(value).casefold()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _copy_exact_keys(values: dict[str, str], source: object, keys: tuple[str, ...]) -> None:
    for key in keys:
        value = _scalar_value(source, key)
        if value:
            values[key] = value


def _copy_alias(values: dict[str, str], target_key: str, source: object, keys: tuple[str, ...]) -> None:
    for key in keys:
        value = _scalar_value(source, key)
        if value:
            values[target_key] = value
            return


def _mapping_value(source: object, key: str) -> object | None:
    if not hasattr(source, "__getitem__"):
        return None
    try:
        value = source[key]  # type: ignore[index]
    except (KeyError, TypeError, AttributeError):
        return None
    return value if _looks_like_mapping(value) else None


def _scalar_value(source: object, key: str) -> str:
    if not hasattr(source, "__getitem__"):
        return ""
    try:
        value = source[key]  # type: ignore[index]
    except (KeyError, TypeError, AttributeError):
        return ""
    if value is None or _looks_like_mapping(value):
        return ""
    return _text(value)


def _looks_like_mapping(value: object) -> bool:
    return hasattr(value, "__getitem__") and hasattr(value, "keys")
