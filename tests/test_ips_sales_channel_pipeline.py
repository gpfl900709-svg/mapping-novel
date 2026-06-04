from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = REPO_ROOT / "ops" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

from ips_sales_channel_pipeline import apply_preset, resolve_live_write


def make_args(preset: str) -> argparse.Namespace:
    return argparse.Namespace(
        preset=preset,
        title_column="",
        platform_column="",
        manager_column="",
        filter_manager="",
        only_empty_column="",
        column_letter="",
        value_column="",
        required_action="",
        write=False,
        dry_run=False,
    )


class IpsSalesChannelPipelinePresetTest(unittest.TestCase):
    def test_current_sheet_preset_targets_s2_column_e_without_manager_filter(self) -> None:
        args = make_args("sheet_blank_sales_channel_content_id")

        apply_preset(args)

        self.assertEqual(args.title_column, "정제_상품명")
        self.assertEqual(args.platform_column, "S2 판매채널")
        self.assertEqual(args.only_empty_column, "S2_판매채널콘텐츠ID")
        self.assertEqual(args.column_letter, "E")
        self.assertEqual(args.filter_manager, "")

    def test_legacy_jo_preset_keeps_old_column_and_manager_scope(self) -> None:
        args = make_args("jo_blank_generated_id")

        apply_preset(args)

        self.assertEqual(args.platform_column, "A")
        self.assertEqual(args.manager_column, "담당자(없을 시 공란)")
        self.assertEqual(args.filter_manager, "조원재")
        self.assertEqual(args.only_empty_column, "생성 ID")
        self.assertEqual(args.column_letter, "D")

    def test_default_pipeline_mode_is_preview_only(self) -> None:
        args = make_args("")

        self.assertFalse(resolve_live_write(args))

    def test_pipeline_live_mode_requires_write_flag(self) -> None:
        args = make_args("")
        args.write = True

        self.assertTrue(resolve_live_write(args))

    def test_pipeline_rejects_write_and_dry_run_together(self) -> None:
        args = make_args("")
        args.write = True
        args.dry_run = True

        with self.assertRaisesRegex(SystemExit, "--write"):
            resolve_live_write(args)


if __name__ == "__main__":
    unittest.main()
