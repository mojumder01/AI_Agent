from google import genai
from google.genai import types
from PIL import Image
import io
import json
import re


_client: genai.Client | None = None


def configure_gemini(api_key: str):
    global _client
    _client = genai.Client(api_key=api_key)


def _build_prompt(row_data: dict, tasks: list[str]) -> str:
    product_info = "\n".join(
        f"- {k}: {v}" for k, v in row_data.items()
        if v and str(v).strip() and k.lower() not in ("image_path", "image path", "ছবির পাথ")
    )

    task_instructions = []
    if "highlights" in tasks:
        task_instructions.append(
            '"highlights": "3-5 টা বুলেট পয়েন্টে প্রোডাক্টের মূল বৈশিষ্ট্য লিখুন (বাংলা বা ইংরেজি)"'
        )
    if "description" in tasks:
        task_instructions.append(
            '"description": "প্রোডাক্টের একটি আকর্ষণীয় বিবরণ লিখুন (2-4 বাক্য)"'
        )
    if "weight" in tasks:
        task_instructions.append(
            '"weight": "প্রোডাক্টের আনুমানিক ওজন (যেমন: 250g, 1kg) — নিশ্চিত না হলে reasonable রেঞ্জ দিন"'
        )
    if "image_quality" in tasks:
        task_instructions.append(
            '"image_quality": "ছবির মান: Good / Average / Poor এবং সংক্ষিপ্ত কারণ"'
        )
    if "watermark" in tasks:
        task_instructions.append(
            '"watermark": "ছবিতে watermark আছে কি না: Yes / No — থাকলে কোথায় উল্লেখ করুন"'
        )

    task_json = ",\n  ".join(task_instructions)

    return f"""আপনি একটি e-commerce product specialist AI।

প্রোডাক্ট তথ্য:
{product_info}

নিচের JSON format-এ উত্তর দিন (শুধু JSON, অন্য কোনো টেক্সট না):
{{
  {task_json}
}}"""


def process_row(
    row_data: dict,
    tasks: list[str],
    image_bytes: bytes | None = None,
    model_name: str = "gemini-2.0-flash",
) -> dict:
    if _client is None:
        return {"error": "API key সেট করা হয়নি"}

    prompt = _build_prompt(row_data, tasks)
    contents: list = [prompt]

    if image_bytes and any(t in tasks for t in ("image_quality", "watermark")):
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img_byte_arr = io.BytesIO()
            fmt = img.format or "JPEG"
            img.save(img_byte_arr, format=fmt)
            mime = f"image/{'jpeg' if fmt.upper() in ('JPG', 'JPEG') else fmt.lower()}"
            contents.insert(
                0,
                types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type=mime),
            )
        except Exception as e:
            pass  # ছবি না থাকলেও টেক্সট দিয়ে চলবে

    try:
        response = _client.models.generate_content(
            model=model_name,
            contents=contents,
        )
        raw = response.text.strip()

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            result = {"error": "JSON parse করা যায়নি", "raw_response": raw[:300]}
    except Exception as e:
        result = {"error": str(e)}

    return result
