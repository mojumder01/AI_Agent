import re


def extract_field(text: str, label: str) -> str:
    """Claude-এর উত্তর থেকে 'Label: value' প্যাটার্ন ধরে নির্দিষ্ট লেবেলের মান বের করে।
    পরের লাইনে আরেকটা 'Word:' লেবেল শুরু হলে সেখানেই থেমে যায়, যাতে দুটো ফিল্ড
    মিশে না যায়।"""
    pattern = rf"^{re.escape(label)}\s*:\s*(.*?)(?=\n[A-Za-z][A-Za-z0-9 _]{{0,30}}:\s|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""
