# AI Product Agent

Claude chat automation — Excel থেকে ডেটা নিয়ে Claude-এ পাঠায়, রেসপন্স Excel-এ সেভ করে।

## প্রথমবার সেটআপ

### Windows (সহজ উপায়)
`run.bat` ফাইলে ডাবল-ক্লিক করুন — এটা automatically virtual environment বানাবে, dependencies ইনস্টল করবে, Playwright Chromium ইনস্টল করবে, এবং অ্যাপ চালু করবে। পরের বার চালাতেও এই একই ফাইলে ডাবল-ক্লিক করলেই হবে।

### Manual (সব OS)
```bash
# 1. ইন্সটল
pip install -r requirements.txt
playwright install chromium

# 2. অ্যাপ চালু
streamlit run app.py
```

## কীভাবে ব্যবহার করবেন

### ধাপ ০ — Claude-এ লগইন করে সেশন সেভ করুন (একবারই লাগবে)
- Sidebar-এ **"🔑 Claude-এ লগইন করুন / সেভ করুন"** চাপুন — একটা ব্রাউজার উইন্ডো খুলবে
- সেই উইন্ডোতে claude.ai-এ normal ভাবে লগইন করুন
- লগইন হয়ে গেলে ব্রাউজার বন্ধ না করে রেখে দিতে পারেন, বা চাইলে সাইডবারের "🔴 Browser বন্ধ করুন" চাপুন — সেশন ডিস্কে সেভ থাকে (`~/.claude_agent_browser_profile`), তাই পরের বার আবার লগইন করা লাগবে না
- সেশন মাঝে মাঝে expire হলে (যেমন claude.ai থেকে জোর করে লগআউট হলে) একই বাটন দিয়ে আবার লগইন করে নিন

### ধাপ ১ — Claude-এ conversation তৈরি করুন
- claude.ai-এ নতুন chat খুলুন
- সেই chat-এ আপনার prompt লিখুন / system instruction দিন
- Chat-এর URL কপি করুন (যেমন: `https://claude.ai/chat/abc-123`)

### ধাপ ২ — App-এ সেটআপ
- Tab সিলেক্ট করুন (Highlights & Description / Weight / Image Check)
- Claude conversation URL দিন
- Output column নাম দিন (default দেওয়া আছে)
- Excel ফাইল আপলোড করুন

### ধাপ ৩ — একটা একটা করে প্রসেস করুন
1. কোন কলামগুলো Claude-এ পাঠাবেন সিলেক্ট করুন
2. **"Claude-এ পাঠাও"** চাপুন
3. Claude উত্তর দিলে UI-তে দেখা যাবে
4. দরকার হলে এডিট করুন
5. **"সেভ ও পরের রো"** চাপুন

> লগইন সেশন expire হয়ে গেলে "Claude-এ পাঠাও" একটা স্পষ্ট error দেখাবে — তখন ধাপ ০ আবার করুন।

## ৩টা Menu

| Menu | কাজ | Output Column |
|------|-----|---------------|
| ✍️ Highlights & Description | পণ্যের বিবরণ লেখা | AI_Highlights_Description |
| ⚖️ Weight | ওজন হিসাব করা | AI_Weight |
| 🖼️ Image Check | ছবির কোয়ালিটি ও watermark | AI_Image_Check |

## Image Check-এর জন্য
Excel-এ একটা কলাম রাখুন যার নামে `image`, `img`, বা `photo` আছে।  
সেই কলামে ছবির **full path** দিন (যেমন: `C:\Products\img001.jpg`)।
