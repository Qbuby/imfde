# -*- coding: utf-8 -*-
"""Gating tests: live render_path against portal/fde.db. No copied HTML builders."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs

SITE = Path(__file__).resolve().parent
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))

import server as S  # noqa: E402


def _qs(raw: str) -> dict:
    return parse_qs(raw, keep_blank_values=False)


class AlignRoomsTest(unittest.TestCase):
    def html(self, path: str, query: str = "") -> str:
        return S.render_path(path, _qs(query))

    def test_case_catalog_is_links_not_inspector(self):
        html = self.html("/案例")
        self.assertNotIn("data-pick", html)
        self.assertNotIn("点一张卡片", html)
        self.assertNotIn("room-gcard", html)
        self.assertIn('class="room room-feed"', html)
        links = re.findall(r'href="(/案例/\d+[^"]*)"', html)
        self.assertGreaterEqual(len(links), 3)

    def test_case_513_empty_orig_keeps_fde_unwritten(self):
        html = self.html("/案例/513")
        self.assertIn("中文全文还在写入", html)
        self.assertNotIn("光刷算法题", html)
        self.assertNotIn("有没有驻场团队", html)
        self.assertNotIn("驻场怎么写的", html)
        self.assertNotIn("为什么要看", html)
        self.assertNotIn("相关开放题", html)

    def test_case_376_cited_numbers_in_orig(self):
        html = self.html("/案例/376")
        orig = html.split('id="原文"', 1)
        self.assertEqual(len(orig), 2)
        orig_html = orig[1].split("</section>", 1)[0]
        self.assertIn("37 步", orig_html)
        self.assertIn("16 次", orig_html)
        self.assertIn("75", orig_html)
        anatomy = html[html.find("落地读法") :]
        if "37 步" in anatomy:
            self.assertIn("37 步", orig_html)

    def test_deploy_no_open_orig_or_marketing_chrome(self):
        html = self.html("/落地", "窗=30")
        self.assertNotIn("打开原文", html)
        self.assertNotIn("访问网站", html)
        self.assertNotIn("对照原文", html)
        self.assertNotIn("部署证据", html)
        self.assertIn("看完整案例", html)
        self.assertIn("往下读就行", html)

    def test_case_detail_has_no_jump_chrome(self):
        html = self.html("/案例/81")
        self.assertNotIn('href="#原文"', html)
        self.assertNotIn("看原文", html)
        self.assertNotIn("公司页译成中文", html)
        self.assertNotIn("读法=", html)
        self.assertNotIn("这个数字怎么来的", html)
        self.assertNotIn("为什么要看", html)
        self.assertNotIn("相关开放题", html)
        self.assertIn("Compiled", html)

    def test_event_page_drops_why_to_look(self):
        html = self.html("/动态/550")
        self.assertNotIn("为什么要看", html)

    def test_learn_home_is_feed(self):
        html = self.html("/方法")
        self.assertIn("往下读就行", html)
        self.assertIn("/方法/discovery", html)
        self.assertNotIn("点一轮圈", html)
        self.assertNotIn("learn-cycle", html)
        self.assertNotIn("为什么要看", html)

    def test_learn_lesson_has_no_audit_or_orig_dump(self):
        html = self.html("/方法/discovery")
        self.assertIn("看完整案例", html)
        self.assertIn("/案例/", html)
        self.assertNotIn("附录 · 还会碰到的现场题", html)
        self.assertNotIn("这不是面试题库", html)
        self.assertNotIn("只列题干", html)
        self.assertNotIn("公司页译成中文", html)
        self.assertNotIn("id=\"原文\"", html)
        self.assertIn("这一步怎么做", html)

    def test_field_has_chinese_orig_essay(self):
        html = self.html("/现场", "窗=30")
        self.assertIn("往下读就行", html)
        self.assertRegex(html, r"[\u4e00-\u9fff]{20,}")
        self.assertTrue(
            "驻场工程师" in html or "驻场" in html,
            "field window should include a Chinese essay paragraph",
        )


if __name__ == "__main__":
    unittest.main()
