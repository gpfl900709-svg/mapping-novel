from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = REPO_ROOT / "ops" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

from secret_redaction import REDACTED, dumps_redacted, redact_string  # noqa: E402


class SecretRedactionTest(unittest.TestCase):
    def test_redacts_known_token_values(self) -> None:
        secret = "abcdefghijklmnopqrstuvwxyz123456"
        text = f"Authorization: Bearer {secret}"

        self.assertNotIn(secret, redact_string(text))
        self.assertIn(REDACTED, redact_string(text))

    def test_redacts_secret_keys_in_nested_payloads(self) -> None:
        clickup_like_token = "pk_" + "A" * 40
        payload = {
            "safe": "visible",
            "headers": {"Authorization": "Bearer " + "B" * 32},
            "api_token": clickup_like_token,
        }

        rendered = dumps_redacted(payload)

        self.assertIn('"safe": "visible"', rendered)
        self.assertNotIn(clickup_like_token, rendered)
        self.assertGreaterEqual(rendered.count(REDACTED), 2)


if __name__ == "__main__":
    unittest.main()
