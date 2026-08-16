import pandas as pd
import io


OUTPUT_COLUMNS = {
    "highlights": "AI_Highlights",
    "description": "AI_Description",
    "weight": "AI_Weight",
    "image_quality": "AI_Image_Quality",
    "watermark": "AI_Watermark_Check",
}


def read_excel(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(file_bytes))


def find_image_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if any(k in col.lower() for k in ("image", "img", "photo", "ছবি", "picture")):
            return col
    return None


def write_output_excel(df: pd.DataFrame, results: list[dict], selected_tasks: list[str]) -> bytes:
    output_df = df.copy()

    for task in selected_tasks:
        col_name = OUTPUT_COLUMNS.get(task, f"AI_{task}")
        output_df[col_name] = ""

    for i, result in enumerate(results):
        if i >= len(output_df):
            break
        if "error" in result:
            for task in selected_tasks:
                col_name = OUTPUT_COLUMNS.get(task, f"AI_{task}")
                output_df.at[i, col_name] = f"Error: {result['error']}"
        else:
            for task in selected_tasks:
                col_name = OUTPUT_COLUMNS.get(task, f"AI_{task}")
                output_df.at[i, col_name] = result.get(task, "")

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        output_df.to_excel(writer, index=False, sheet_name="Results")

        ws = writer.sheets["Results"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    buffer.seek(0)
    return buffer.read()
