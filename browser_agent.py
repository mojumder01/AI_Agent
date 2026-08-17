import sys
import asyncio

# Streamlit (Tornado) forces the Windows event loop policy to Selector-based,
# which can't spawn subprocesses — Playwright's sync API needs Proactor for that.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.sync_api import sync_playwright
import threading
import queue
import time
import os


PROFILE_DIR = os.path.expanduser("~/.claude_agent_browser_profile")


class ClaudeAgent:
    """
    Playwright's sync API pins the browser session to whichever OS thread
    started it. Streamlit runs each rerun (each button click) on a fresh
    thread, so a naive "store the agent in session_state and call it again
    later" breaks with `greenlet.error: cannot switch to a different thread`.

    This class keeps the whole Playwright session inside one dedicated
    background thread that stays alive across reruns; every public method
    just enqueues a job for that thread and blocks for the result.
    """

    def __init__(self):
        self._req_q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._start_error: Exception | None = None
        self._page = None
        self._context = None
        self._pw = None

    # ── Worker thread lifecycle ─────────────────────────────────────────────

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._started.wait(timeout=60):
            raise TimeoutError("ব্রাউজার চালু হতে দেরি হচ্ছে।")
        if self._start_error:
            raise self._start_error

    def _run(self):
        try:
            os.makedirs(PROFILE_DIR, exist_ok=True)
            self._pw = sync_playwright().start()
            launch_kwargs = dict(
                user_data_dir=PROFILE_DIR,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1200, "height": 800},
            )
            try:
                # আসল ইনস্টল করা Chrome ব্যবহার করলে claude.ai কম bot হিসেবে ধরে —
                # bundled Chromium দিয়ে সেশন বারবার লগআউট হয়ে যাওয়ার সমস্যা কমে।
                self._context = self._pw.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
            except Exception:
                self._context = self._pw.chromium.launch_persistent_context(**launch_kwargs)
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        except Exception as e:
            self._start_error = e
            self._started.set()
            return

        self._started.set()

        while True:
            job = self._req_q.get()
            if job is None:
                break
            job()

        try:
            if self._context:
                self._context.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    def _call(self, fn, timeout=180):
        """worker থ্রেডে fn() রান করে এবং রেজাল্ট/এরর ফেরত দেয়।"""
        result = {}
        event = threading.Event()

        def wrapped():
            try:
                result["value"] = fn()
            except Exception as e:
                result["error"] = e
            finally:
                event.set()

        self._req_q.put(wrapped)
        if not event.wait(timeout=timeout):
            raise TimeoutError("ব্রাউজার থ্রেড সাড়া দিচ্ছে না (timeout)।")
        if "error" in result:
            raise result["error"]
        return result.get("value")

    # ── Public API (safe to call from any thread; runs on the worker) ──────

    def go_to_conversation(self, url: str):
        def job():
            self._page.goto(url, wait_until="domcontentloaded")
            time.sleep(2)
        self._call(job)

    def open_login(self):
        """লগইন/সেশন সেভ করার জন্য claude.ai খোলে — ইউজার ম্যানুয়ালি লগইন করবেন।"""
        def job():
            self._page.goto("https://claude.ai", wait_until="domcontentloaded")
            time.sleep(1)
        self._call(job)

    def send_message(self, text: str, image_path: str | None = None) -> str:
        """টেক্সট (এবং ছবি) Claude chat-এ পাঠায় এবং রেসপন্স রিটার্ন করে।"""
        return self._call(lambda: self._send_message_impl(text, image_path))

    def is_alive(self) -> bool:
        try:
            return (
                self._thread is not None
                and self._thread.is_alive()
                and self._page is not None
                and not self._page.is_closed()
            )
        except Exception:
            return False

    def close(self):
        try:
            self._req_q.put(None)  # sentinel — worker loop closes context/pw and exits
            if self._thread:
                self._thread.join(timeout=15)
        except Exception:
            pass
        self._page = None
        self._context = None
        self._pw = None

    # ── Worker-thread-only internals (never call these directly) ───────────

    def _is_logged_in(self) -> bool:
        try:
            url = self._page.url
            if "login" in url or "/auth" in url:
                return False
            if self._page.locator('input[type="email"]').count() > 0:
                return False
            if self._page.get_by_text("Log in", exact=False).count() > 0:
                return False
            return True
        except Exception:
            return True

    def _send_message_impl(self, text: str, image_path: str | None) -> str:
        if not self._is_logged_in():
            raise RuntimeError(
                "Claude সেশন লগইন করা নেই। সাইডবার থেকে 'Claude-এ লগইন করুন / সেভ করুন' "
                "বাটনে ক্লিক করে ব্রাউজার উইন্ডোতে লগইন করুন, তারপর আবার পাঠান।"
            )

        # ইনপুট বক্স খোঁজা
        input_selectors = [
            'div[contenteditable="true"]',
            'div[data-lexical-editor="true"]',
            'div.ProseMirror',
        ]
        input_box = None
        for sel in input_selectors:
            try:
                self._page.wait_for_selector(sel, timeout=8000)
                boxes = self._page.locator(sel).all()
                if boxes:
                    input_box = boxes[-1]
                    break
            except Exception:
                continue

        if input_box is None:
            raise RuntimeError("Claude-এর input box পাওয়া যায়নি। পেজ ঠিকমতো লোড হয়েছে কিনা দেখুন।")

        # ছবি আটাচ করা (image check task-এর জন্য)
        if image_path and os.path.exists(image_path):
            self._attach_image(image_path)
            time.sleep(1)

        # টেক্সট টাইপ করা
        input_box.click()
        time.sleep(0.3)
        # আগের টেক্সট মুছে দেওয়া
        input_box.press("Control+a")
        input_box.press("Backspace")
        time.sleep(0.2)
        # নতুন টেক্সট পেস্ট (type-এর চেয়ে দ্রুত)
        self._page.evaluate(
            """(text) => {
                const el = document.querySelector('div[contenteditable="true"]:last-of-type') ||
                           document.querySelector('div[contenteditable="true"]');
                if (el) {
                    el.focus();
                    document.execCommand('insertText', false, text);
                }
            }""",
            text,
        )
        time.sleep(0.5)

        # Enter চেপে পাঠানো
        input_box.press("Enter")
        time.sleep(1)

        # রেসপন্স আসা পর্যন্ত অপেক্ষা
        return self._wait_for_response()

    def _attach_image(self, image_path: str):
        """ছবি আটাচ করার চেষ্টা করে।"""
        try:
            file_input = self._page.locator('input[type="file"]').first
            file_input.set_input_files(image_path)
        except Exception:
            # ফাইল ইনপুট না থাকলে ক্লিপবোর্ড দিয়ে চেষ্টা
            try:
                self._page.evaluate("""
                    async (path) => {
                        const response = await fetch('file://' + path);
                        const blob = await response.blob();
                        const item = new ClipboardItem({ [blob.type]: blob });
                        await navigator.clipboard.write([item]);
                    }
                """, image_path)
                input_box = self._page.locator('div[contenteditable="true"]').last
                input_box.press("Control+v")
            except Exception:
                pass

    def _wait_for_response(self) -> str:
        """Claude-এর স্ট্রিমিং শেষ হওয়া পর্যন্ত অপেক্ষা করে রেসপন্স রিটার্ন করে।"""
        # স্ট্রিমিং শুরু হওয়ার জন্য একটু অপেক্ষা
        time.sleep(3)

        # Stop বাটন দেখা যাচ্ছে কিনা চেক করে অপেক্ষা
        stop_selectors = [
            'button[aria-label="Stop"]',
            'button[aria-label="Stop generating"]',
            'button[data-testid="stop-button"]',
        ]
        max_wait = 120
        start = time.time()

        while time.time() - start < max_wait:
            found_stop = False
            for sel in stop_selectors:
                if self._page.locator(sel).count() > 0:
                    found_stop = True
                    break
            if not found_stop:
                break
            time.sleep(1)

        # এক্সট্রা রেন্ডারের জন্য অপেক্ষা
        time.sleep(1.5)

        return self._extract_last_response()

    def _extract_last_response(self) -> str:
        """পেজ থেকে Claude-এর শেষ রেসপন্স বের করে।"""
        # সবচেয়ে বাইরের কন্টেইনার আগে চেষ্টা করা হয় — নেস্টেড '.prose' মাঝেমধ্যে
        # পুরো উত্তরের বদলে শুধু একটা অংশ (যেমন একটা রিচ-টেক্সট/ডিফ ব্লক) ধরে,
        # যার ফলে বাকি অংশ (Highlights ইত্যাদি) হারিয়ে যায়।
        selectors = [
            '[data-message-author-role="assistant"]',
            '[data-message-author-role="assistant"] .prose',
            '.font-claude-message',
        ]
        for sel in selectors:
            elements = self._page.locator(sel).all()
            if elements:
                return elements[-1].inner_text().strip()

        # Fallback: সব মেসেজ বক্স থেকে শেষটা
        all_msgs = self._page.locator('.whitespace-pre-wrap').all()
        if all_msgs:
            return all_msgs[-1].inner_text().strip()

        return ""
