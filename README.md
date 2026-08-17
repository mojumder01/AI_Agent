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
2. **"Claude-এ পাঠাও"** চাপুন → ব্রাউজার খুলবে
3. প্রথমবার: Claude-এ লগইন করুন (পরের বার মনে থাকবে)
4. Claude উত্তর দিলে UI-তে দেখা যাবে
5. দরকার হলে এডিট করুন
6. **"সেভ ও পরের রো"** চাপুন

## ৩টা Menu

| Menu | কাজ | Output Column |
|------|-----|---------------|
| ✍️ Highlights & Description | পণ্যের বিবরণ লেখা | AI_Highlights_Description |
| ⚖️ Weight | ওজন হিসাব করা | AI_Weight |
| 🖼️ Image Check | ছবির কোয়ালিটি ও watermark | AI_Image_Check |

## Image Check-এর জন্য
Excel-এ একটা কলাম রাখুন যার নামে `image`, `img`, বা `photo` আছে।  
সেই কলামে ছবির **full path** দিন (যেমন: `C:\Products\img001.jpg`)।
