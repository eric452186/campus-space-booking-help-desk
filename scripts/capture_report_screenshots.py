"""Capture reproducible screenshots from the locally running Gradio app."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "report" / "screenshots"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def submit(page: Page, message: str, answer_marker: str) -> None:
    bot_messages = page.locator('[aria-label^="bot\'s message"]')
    previous_count = bot_messages.count()
    page.get_by_label("你的問題", exact=True).fill(message)
    page.get_by_role("button", name="送出", exact=True).click()
    expect(bot_messages).to_have_count(previous_count + 1, timeout=120_000)
    answer = bot_messages.last.inner_text()
    if answer_marker not in answer:
        raise AssertionError(
            f"Expected answer marker {answer_marker!r}, received: {answer!r}"
        )


def clear(page: Page) -> None:
    page.get_by_role("button", name="清除對話", exact=True).click()
    page.get_by_text("已清除對話", exact=False).wait_for(
        state="visible", timeout=15_000
    )


def capture(page: Page, filename: str) -> None:
    page.locator(".gradio-container").screenshot(
        path=OUTPUT_DIR / filename,
        animations="disabled",
    )


def main() -> None:
    if not CHROME.exists():
        raise FileNotFoundError(f"Chrome was not found at {CHROME}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(CHROME),
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto("http://127.0.0.1:7860", wait_until="domcontentloaded")
        page.get_by_role("heading", name="校園空間預約服務台").wait_for(
            state="visible", timeout=30_000
        )
        page.get_by_role("button", name="重設示範資料", exact=True).click()

        submit(
            page,
            "在圖書館討論室可以吃便當嗎？請引用規章來源。",
            "不可用餐",
        )
        capture(page, "conversation_1_rag.png")

        clear(page)
        submit(
            page,
            "請查詢2026-11-06 14:00到16:00可容納12人的空間。",
            "工程館 A101",
        )
        submit(
            page,
            "請建立預約：空間 ENG-A101，日期 2026-11-06，"
            "時間 14:00 到 16:00，用途是期中專題討論。",
            "BK0001",
        )
        capture(page, "conversation_2_booking.png")

        clear(page)
        submit(page, "Where is booking B9999?", "找不到這筆資料")
        capture(page, "conversation_3_missing.png")

        clear(page)
        submit(
            page,
            "請查詢預約編號 BK0001，確認資料已儲存。",
            "已確認",
        )
        capture(page, "saved_data_evidence.png")
        browser.close()

    for path in sorted(OUTPUT_DIR.glob("*.png")):
        print(path)


if __name__ == "__main__":
    main()
