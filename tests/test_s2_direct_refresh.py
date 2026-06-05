from __future__ import annotations

import unittest

from s2_direct_refresh import (
    build_s2_direct_refresh_config,
    normalize_s2_direct_refresh_secret_values,
)


class S2DirectRefreshTest(unittest.TestCase):
    def test_direct_refresh_is_disabled_by_default(self) -> None:
        config = build_s2_direct_refresh_config({})

        self.assertFalse(config.enabled)
        self.assertFalse(config.is_ready)
        self.assertFalse(config.is_authorized("anything"))

    def test_enabled_refresh_requires_admin_token_by_default(self) -> None:
        config = build_s2_direct_refresh_config({"S2_DIRECT_REFRESH_ENABLED": "true"})

        self.assertTrue(config.enabled)
        self.assertTrue(config.require_token)
        self.assertFalse(config.token_ready)
        self.assertFalse(config.is_ready)

    def test_admin_token_authorizes_direct_refresh(self) -> None:
        config = build_s2_direct_refresh_config(
            {
                "S2_DIRECT_REFRESH_ENABLED": "true",
                "S2_DIRECT_REFRESH_TOKEN": "secret-token",
            }
        )

        self.assertTrue(config.is_ready)
        self.assertTrue(config.is_authorized("secret-token"))
        self.assertFalse(config.is_authorized("wrong-token"))
        self.assertFalse(config.is_authorized(""))

    def test_token_requirement_can_be_disabled_explicitly(self) -> None:
        config = build_s2_direct_refresh_config(
            {
                "S2_DIRECT_REFRESH_ENABLED": "true",
                "S2_DIRECT_REFRESH_REQUIRE_TOKEN": "false",
            }
        )

        self.assertTrue(config.is_ready)
        self.assertTrue(config.is_authorized(""))

    def test_streamlit_section_secrets_are_normalized(self) -> None:
        values = normalize_s2_direct_refresh_secret_values(
            {
                "s2_refresh": {
                    "enabled": "true",
                    "admin_token": "section-token",
                    "require_token": "true",
                }
            }
        )

        config = build_s2_direct_refresh_config(values)

        self.assertTrue(config.enabled)
        self.assertTrue(config.require_token)
        self.assertTrue(config.is_authorized("section-token"))


if __name__ == "__main__":
    unittest.main()
