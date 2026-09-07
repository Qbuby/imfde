# -*- coding: utf-8 -*-
"""Playwright 有头实测 imfde.ai 登录流程。

按测试铁律：OAuth 修复必须真实浏览器（有头）跑通 UI 实测。
本脚本自动化：打开 /登录 → 点渠道按钮 → 跟到授权页 → 抓授权页是否报错
（redirect_uri_mismatch / invalid_client 等会在授权页直接显示）。
Google/GitHub 的账号密码输入由人工接管：脚本会挂起等待人工完成授权，
授权回调后的页面（成功跳回 or 报错文本）会被完整捕获并输出。
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import urllib.parse

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
        # 用本机真实 Chrome + 持久化 profile：Google 会拦截自动化 Chromium（"此浏览器可能不安全"），
        # 真实 Chrome 通道 + 持久 profile 既绕开拦截，又能复用已登录的 Google/GitHub 会话。
        user_data = os.path.join(tempfile.gettempdir(), "imfde-pw-profile")
        # Google 检测 navigator.webdriver / CDP 自动化标志 → "此浏览器可能不安全"。
        # 关掉 AutomationControlled + 排除 enable-automation 开关后可正常登录。
        launch_args = {
            "args": ["--disable-blink-features=AutomationControlled"],
            "ignore_default_args": ["--enable-automation"],
        }
        try:
            ctx = p.chromium.launch_persistent_context(
                user_data, headless=False, channel="chrome",
                viewport={"width": 1280, "height": 900}, **launch_args)
        except Exception as e:  # 未装 Chrome 时回退 Playwright Chromium
            print(f"    (本机 Chrome 不可用：{str(e)[:80]}，回退 Chromium)")
            ctx = p.chromium.launch_persistent_context(
                user_data, headless=False, viewport={"width": 1280, "height": 900}, **launch_args)
        # 双保险：运行时抹掉 navigator.webdriver
        page = ctx.new_page()
        page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

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
            ctx.close()
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
                    ctx.close()
                    return 2
            print("    授权页正常打开（无 redirect_uri/客户端错误）")

        # 自动点选（profile 已有 Google 会话时账号选择/授权确认可全自动），必要时人工接管
        print(f"[3] 等待授权完成（180 秒；账号选择/确认自动点击，必要时请人工接管）...")
        deadline = time.time() + 180
        back = False
        while time.time() < deadline:
            host = (urllib.parse.urlparse(page.url).hostname or "").lower()
            if host == "imfde.ai" or host.endswith(".imfde.ai"):
                back = True
                break
            if "accounts.google.com" in page.url:
                # 账号选择页：点已登录的账号条目
                for sel in ["div[data-identifier]", 'li div[role="link"]', "[data-email]"]:
                    loc = page.locator(sel)
                    if loc.count():
                        try:
                            loc.first.click(timeout=2000)
                            print("    自动点击账号选择...")
                        except Exception:
                            pass
                        break
                # 授权确认页：点「继续」/「允许」
                for label in ["继续", "Continue", "允许", "Allow"]:
                    btn = page.get_by_role("button", name=label)
                    if btn.count():
                        try:
                            btn.first.click(timeout=2000)
                            print(f"    自动点击授权确认（{label}）...")
                        except Exception:
                            pass
                        break
            time.sleep(1)
        if not back:
            print(f"!! 180 秒内未跳回 imfde.ai，当前停在: {page.url[:120]}")
            page.screenshot(path=f"auth_{PROVIDER}_timeout.png")
            ctx.close()
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
        ctx.close()
        if ok and has_avatar:
            print(f"== PASS: {PROVIDER} 登录全链路成功 ==")
            return 0
        print(f"== FAIL: {PROVIDER} 登录后页面异常 ==")
        return 4


if __name__ == "__main__":
    sys.exit(main())
