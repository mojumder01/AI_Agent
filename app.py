import streamlit as st
import zipfile
import io
import time
from agent import configure_gemini, process_row
from excel_handler import read_excel, find_image_column, write_output_excel

st.set_page_config(
    page_title="AI Product Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 AI Product Agent")
st.caption("Excel ফাইল আপলোড করুন → AI দিয়ে Highlights, Description, Weight, Image Quality অটো তৈরি করুন")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    api_key = st.text_input(
        "Google Gemini API Key",
        type="password",
        placeholder="AIza...",
        help="aistudio.google.com থেকে ফ্রি API key নিন",
    )

    st.divider()
    st.subheader("কোন কাজগুলো করবে?")
    do_highlights = st.checkbox("✍️ Highlights লেখা", value=True)
    do_description = st.checkbox("📝 Description লেখা", value=True)
    do_weight = st.checkbox("⚖️ Weight হিসাব করা", value=True)
    do_image_quality = st.checkbox("🖼️ Image Quality চেক", value=True)
    do_watermark = st.checkbox("💧 Watermark চেক", value=True)

    selected_tasks = []
    if do_highlights:
        selected_tasks.append("highlights")
    if do_description:
        selected_tasks.append("description")
    if do_weight:
        selected_tasks.append("weight")
    if do_image_quality:
        selected_tasks.append("image_quality")
    if do_watermark:
        selected_tasks.append("watermark")

    st.divider()
    model_name = st.selectbox(
        "Gemini Model",
        ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
        help="Flash = দ্রুত ও ফ্রি। Pro = বেশি accurate।",
    )

# ── Main Area ────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📊 Excel ফাইল")
    excel_file = st.file_uploader(
        "Input Excel আপলোড করুন (.xlsx)",
        type=["xlsx", "xls"],
    )

with col2:
    st.subheader("🖼️ ছবির ফোল্ডার (ZIP)")
    images_zip = st.file_uploader(
        "সব ছবি একটা ZIP-এ দিন (না থাকলে খালি রাখুন)",
        type=["zip"],
        help="ZIP-এর ভেতরে ছবিগুলো রাখুন। Excel-এ image column-এর নামের সাথে ফাইল নাম মিলতে হবে।",
    )

# ── Preview ───────────────────────────────────────────────────────────────────
if excel_file:
    df = read_excel(excel_file.read())
    excel_file.seek(0)

    st.divider()
    st.subheader(f"ডেটা Preview — {len(df)} রো পাওয়া গেছে")
    st.dataframe(df.head(5), use_container_width=True)

    img_col = find_image_column(df)
    if img_col:
        st.info(f"Image column detected: **{img_col}**")
    else:
        st.warning("Image column পাওয়া যায়নি। Column নামে 'image', 'img', 'photo' বা 'ছবি' থাকলে auto-detect হবে।")

# ── Run ───────────────────────────────────────────────────────────────────────
st.divider()

run_btn = st.button(
    "🚀 Agent চালু করো",
    type="primary",
    disabled=not (excel_file and api_key and selected_tasks),
)

if not api_key:
    st.warning("Sidebar-এ Gemini API Key দিন।")
if not selected_tasks:
    st.warning("অন্তত একটা কাজ সিলেক্ট করুন।")

if run_btn:
    configure_gemini(api_key)

    df = read_excel(excel_file.read())

    # ZIP থেকে ছবি লোড করা
    image_map: dict[str, bytes] = {}
    if images_zip:
        with zipfile.ZipFile(io.BytesIO(images_zip.read())) as zf:
            for name in zf.namelist():
                if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    basename = name.split("/")[-1]
                    image_map[basename] = zf.read(name)
        st.success(f"{len(image_map)} টি ছবি লোড হয়েছে।")

    img_col = find_image_column(df)

    results = []
    progress = st.progress(0, text="শুরু হচ্ছে...")
    status_box = st.empty()
    total = len(df)

    for i, row in df.iterrows():
        row_dict = row.to_dict()
        status_box.info(f"প্রসেস হচ্ছে: রো {i + 1} / {total}")

        # ছবি খোঁজা
        img_bytes = None
        if img_col and img_col in row_dict:
            img_name = str(row_dict[img_col]).strip().split("/")[-1]
            img_bytes = image_map.get(img_name)

        result = process_row(
            row_data=row_dict,
            tasks=selected_tasks,
            image_bytes=img_bytes,
            model_name=model_name,
        )
        results.append(result)
        progress.progress((i + 1) / total, text=f"সম্পন্ন: {i + 1}/{total}")
        time.sleep(0.3)  # rate limit এড়াতে

    status_box.success("সব রো প্রসেস সম্পন্ন!")

    # Output Excel তৈরি
    output_bytes = write_output_excel(df, results, selected_tasks)

    st.download_button(
        label="⬇️ Output Excel ডাউনলোড করুন",
        data=output_bytes,
        file_name="ai_product_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # Result preview
    st.subheader("Result Preview (প্রথম ৫ রো)")
    import pandas as pd
    result_df = pd.DataFrame(results[:5])
    st.dataframe(result_df, use_container_width=True)
