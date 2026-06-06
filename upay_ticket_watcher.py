import re
import time
import sys
import subprocess
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

UPAY_URL = "https://upay.co.uk/app/"
BOT_TOKEN = "8942122984:AAF-gW7AhfvCv65zqHwhMC2GYQt2-P9NB4I"
CHAT_ID = "6604599029"

CHECK_EVERY_SECONDS = 120
PROFILE_DIR = Path("./upay_profile")

EVENT_TEXT = "Formal Hall Dinner 2026"
DATE_BUTTON_TEXT = "Choose Date(s)"

def notify(message: str) -> None:
    print("\n" + "=" * 80)
    print(message)
    print("=" * 80 + "\n")
    print("\a", end="", flush=True)

    try:
        requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": message},
            timeout=10,
        )
    except Exception:
        pass

    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "UPay watcher"',
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def click_if_visible(page, text: str) -> bool:
    try:
        loc = page.get_by_text(text, exact=False)
        if loc.count() > 0:
            loc.first.click(timeout=3000)
            return True
    except Exception:
        pass

    try:
        btn = page.get_by_role("button", name=re.compile(re.escape(text), re.I))
        if btn.count() > 0:
            btn.first.click(timeout=3000)
            return True
    except Exception:
        pass

    return False


def body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000).lower()
    except Exception:
        return ""


def debug_screenshot(page, name="upay_debug.png"):
    try:
        page.screenshot(path=name, full_page=True)
        print(f"[DEBUG] Saved screenshot to {name}")
    except Exception as e:
        print(f"[DEBUG] Screenshot failed: {e!r}")


def check_once(page) -> bool:
    print(f"[{time.strftime('%H:%M:%S')}] Refreshing page...")
    page.reload(wait_until="domcontentloaded")
    time.sleep(1.5)

    print(f"[{time.strftime('%H:%M:%S')}] Clicking event...")
    try:
        page.get_by_text(
            "Formal Hall Dinner 2026 - Dining Hall",
            exact=False
        ).first.click(timeout=4000)
    except Exception:
        try:
            page.get_by_text(
                "Formal Hall Dinner 2026",
                exact=False
            ).first.click(timeout=4000)
        except Exception:
            print(f"[{time.strftime('%H:%M:%S')}] Could not click event text.")

    time.sleep(1.5)

    print(f"[{time.strftime('%H:%M:%S')}] Clicking Choose Date(s)...")
    try:
        choose = page.get_by_text(
            re.compile(r"Choose Date\(s\)", re.I)
        )

        if choose.count() > 0:
            choose.first.scroll_into_view_if_needed()
            choose.first.click(timeout=4000, force=True)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Could not find Choose Date(s).")

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Choose Date(s) click failed: {e!r}")

    time.sleep(1.5)

    debug_screenshot(page)

    text = body_text(page)

    print(f"[{time.strftime('%H:%M:%S')}] BODY DEBUG:")
    print(text[:1000])

    matches = re.findall(r"(\d+)\s+tickets?\s+left", text)

    if matches:
        best = max(int(x) for x in matches)

        if best > 0:
            notify(f"Tickets may be available: {best} left")
            return True

        print(f"[{time.strftime('%H:%M:%S')}] Still sold out (0 tickets left).")
        return False

    if (
        "0 tickets left" in text
        or "sold out" in text
        or "no ticket available for this date" in text
    ):
        print(f"[{time.strftime('%H:%M:%S')}] Still sold out.")
        return False

    print(f"[{time.strftime('%H:%M:%S')}] No clear ticket count found.")
    return False

def main():

    print("Starting browser...")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
        )
        print("Browser launched.")

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print("Navigating to UPay...")
        page.goto(UPAY_URL, wait_until="domcontentloaded", timeout=30000)
        print("Navigation done.")

        notify("Browser opened. Log in if needed, then leave it running.")

        while True:
            try:
                found = check_once(page)
                if found:
                    break
            except PlaywrightTimeoutError:
                print(f"[{time.strftime('%H:%M:%S')}] Timeout, retrying.")
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Error: {e!r}")

            time.sleep(CHECK_EVERY_SECONDS)

        input("Press Enter to close the browser...")
        ctx.close()


if __name__ == "__main__":
    main()
