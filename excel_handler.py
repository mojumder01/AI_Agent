import pandas as pd
import io
import os


def load_excel(path: str) -> pd.DataFrame:
    return pd.read_excel(path, dtype=str).fillna("")


def save_result(df: pd.DataFrame, row_idx: int, column: str, value: str, path: str) -> pd.DataFrame:
    """একটি নির্দিষ্ট সেলে ভ্যালু সেভ করে ফাইল আপডেট করে।"""
    if column not in df.columns:
        df[column] = ""
    df.at[row_idx, column] = value

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
        ws = writer.sheets["Sheet1"]
        for col in ws.columns:
            max_len = max((len(str(cell.value or "")) for cell in col), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    return df


def find_image_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if any(k in col.lower() for k in ("image", "img", "photo", "ছবি", "picture")):
            return col
    return None


def get_next_empty_row(df: pd.DataFrame, column: str) -> int | None:
    """যে কলামে এখনো ভ্যালু নেই সেই রো-এর ইন্ডেক্স দেয়।"""
    if column not in df.columns:
        return 0
    for i, val in enumerate(df[column]):
        if not str(val).strip() or str(val).strip() == "nan":
            return i
    return None


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)
    return buf.read()
