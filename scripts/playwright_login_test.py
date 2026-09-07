# -*- coding: utf-8 -*-
"""Playwright 有头实测 imfde.ai 登录流程。

按测试铁律：OAuth 修复必须真实浏览器（有头）跑通 UI 实测。
本脚本自动化：打开 /登录 → 点渠道按钮 → 跟到授权页 → 抓授权页是否报错
（redirect_uri_mismatch / invalid_client 等会在授权页直接显示）。
Google/GitHub 的账号密码输入由人工接管：脚本会挂起等待人工完成授权，
授权回调后的页面（成功跳回 or 报错文本）会被完整捕获并输出。
"""
from __future__ import annotations

import sys
import time

from playwright.sync_api import sync_playwright

PROVIDER = sys.argv[1] if len(sys.argv) > 1 else "google"
BASE = "https://imfde.ai"

SELECTORS = {
    "github": "a.auth-gh",
    "google": "a.auth-google",
    "wechat": "a.auth-wechat",
}


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 有头模式（铁律）
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)

        print(f"[1] 打开 {BASE}/登录 ...")
        page.goto(f"{BASE}/登录", wait_until="networkidle")
        btns = page.locator(".auth-btn").all_inner_texts()
        print(f"    登录页按钮: {btns}")

        sel = SELECTORS.get(PROVIDER)
        if not sel or not page.locator(sel).count():
            print(f"!! 渠道 {PROVIDER} 按钮不存在（凭据未配或选择器错）")
            browser.close()
            return 1

        print(f"[2] 点击 {PROVIDER} 登录按钮 ...")
        page.click(sel)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1500)
        print(f"    当前 URL: {page.url[:120]}")

        # 若在授权域：检查授权页是否直接报错
        if "google" in page.url or "github" in page.url or "weixin" in page.url:
            content = page.content()
            for bad in ("redirect_uri_mismatch", "invalid_client", "Error 400", "invalid_request",
                        "access_denied", "应用未上线", "非法"):
                if bad.lower() in content.lower():
                    print(f"!! 授权页报错: {bad}")
                    print("    页面文本片段:", page.inner_text("body")[:400].replace("\n", " | "))
                    page.screenshot(path=f"auth_{PROVIDER}_authorize_error.png")
                    browser.close()
                    return 2
            print("    授权页正常打开（无 redirect_uri/客户端错误）")

        # 人工接管：账号密码/扫码由测试者完成；脚本轮询等待跳回 imfde.ai
        print(f"[3] 请在浏览器窗口完成 {PROVIDER} 授权（120 秒内）。脚本等待跳回 imfde.ai ...")
        deadline = time.time() + 120
        result = "timeout"
        while time.time() < deadline:
            url = page.url
            if "imfde.ai" in url:
                result = "returned"
                break
            time.sleep(1)
        if result == "timeout":
            print("!! 120 秒内未跳回（未完成授权或回调未发生）")
            page.screenshot(path=f"auth_{PROVIDER}_timeout.png")
            browser.close()
            return 3

        print(f"[4] 已跳回: {page.url[:120]}")
        page.wait_for_load_state("domcontentloaded")
        body = page.inner_text("body")[:500].replace("\n", " | ")
        print(f"    页面文本: {body}")

        ok = ("登录失败" not in body) and ("Internal Server Error" not in body) and ("Traceback" not in body)
        # 成功的标志：导航栏出现头像/昵称（auth-entry on）
        has_avatar = page.locator(".auth-entry.on").count() > 0
        print(f"    头像导航: {'有' if has_avatar else '无'}")
        page.screenshot(path=f"auth_{PROVIDER}_result.png")
        if errors:
            print("!! 过程中捕获的 HTTP/JS 错误:")
            for e in errors[:10]:
                print("   ", e[:150])
        browser.close()
        if ok and has_avatar:
            print(f"== PASS: {PROVIDER} 登录全链路成功 ==")
            return 0
        print(f"== FAIL: {PROVIDER} 登录后页面异常 ==")
        return 4


if __name__ == "__main__":
    sys.exit(main())
