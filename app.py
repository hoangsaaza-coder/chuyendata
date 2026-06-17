import base64
import io
import json
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st
from openai import OpenAI
from PIL import Image

FIELDS = [
    "KHÁCH HÀNG", "Tt", "SĐT", "ĐỊA CHỈ", "SẢN PHẨM", "KÍCH THƯỚC",
    "SL", "TỔNG ĐƠN", "GHI CHÚ", "NGUỒN ĐƠN", "NGƯỜI BÁN"
]

PRODUCT_RULES = """
Quy tắc chuẩn hóa sản phẩm:
- Nệm Foam Việt Nhật Nano / Foam Nano -> FOAM NANO.
- Nệm cao su thiên nhiên -> CAO SU THIÊN NHIÊN.
- Nệm foam gấp 3 -> FOAM GẤP 3.
- Nếu hóa đơn có nhiều món, chỉ lấy sản phẩm chính là nệm. Quà tặng / gối / ga / phụ kiện đưa vào GHI CHÚ nếu cần.
- Kích thước lấy từ tên sản phẩm hoặc ghi chú. Chuẩn hóa dạng ví dụ: 1m7x1m8x15cm, 180x200x15cm, 1m6x2mx10cm.
- TỔNG ĐƠN ưu tiên lấy "Tổng thanh toán", không lấy "Thành tiền" trước khuyến mại.
- NGƯỜI BÁN lấy tên cuối trong dòng nhân viên / thu ngân, ví dụ "SOL1 - Trần Hoàng Sa" -> "Hoàng Sa".
- Tt để trống nếu ảnh không có thông tin trạng thái.
- NGUỒN ĐƠN để trống nếu ảnh không có.
"""

SYSTEM_PROMPT = f"""
Bạn là trợ lý trích xuất dữ liệu đơn hàng từ ảnh hóa đơn bán nệm.
Trả về DUY NHẤT một JSON object hợp lệ, không markdown, không giải thích.
JSON phải có đúng các key sau: {FIELDS}
{PRODUCT_RULES}
Nếu không đọc được trường nào thì để chuỗi rỗng "".
SĐT chỉ lấy số điện thoại, bỏ chữ thừa.
SL là số lượng của sản phẩm chính, nếu không chắc thì để 1.
TỔNG ĐƠN giữ định dạng tiền Việt Nam có dấu chấm, ví dụ 2.850.000.
GHI CHÚ gom các thông tin cọc, thu hộ, quà, bộ ga, yêu cầu đặc biệt.
"""


def image_to_data_url(uploaded_file) -> str:
    data = uploaded_file.getvalue()
    mime = uploaded_file.type or "image/png"
    return f"data:{mime};base64," + base64.b64encode(data).decode("utf-8")


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        obj = json.loads(match.group(0))
    return {field: str(obj.get(field, "")) for field in FIELDS}


def call_openai(api_key: str, data_url: str, extra_note: str) -> dict:
    client = OpenAI(api_key=api_key)
    user_text = "Hãy đọc ảnh hóa đơn và xuất theo form đã yêu cầu."
    if extra_note.strip():
        user_text += "\nGhi chú bổ sung từ người dùng: " + extra_note.strip()

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_text},
                    {"type": "input_image", "image_url": data_url},
                ],
            },
        ],
        temperature=0,
    )
    return extract_json(response.output_text)


def make_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


st.set_page_config(page_title="Xuất dữ liệu đơn hàng Nệm Việt Nhật", layout="wide")
st.title("Xuất dữ liệu đơn hàng từ ảnh")
st.caption("Upload ảnh hóa đơn → AI đọc dữ liệu → chỉnh lại nếu cần → tải CSV hoặc copy dán vào Google Sheet.")

def get_default_api_key() -> str:
    try:
        return st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        return os.getenv("OPENAI_API_KEY", "")


with st.sidebar:
    st.header("Cấu hình")
    default_api_key = get_default_api_key()
    if default_api_key:
        st.success("Đã cấu hình OPENAI_API_KEY trong Secrets/Environment.")
    api_key = st.text_input("OpenAI API key", type="password", value=default_api_key)
    st.caption("Khi deploy online, nên lưu key trong Streamlit Secrets, không đưa key vào code.")
    extra_note = st.text_area(
        "Ghi chú quy tắc riêng",
        placeholder="Ví dụ: Nguồn đơn mặc định là Tiktok Nệm Việt Nhật, người bán mặc định Hoàng Sa...",
        height=120,
    )

uploaded_files = st.file_uploader(
    "Chọn 1 hoặc nhiều ảnh hóa đơn", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True
)

if "rows" not in st.session_state:
    st.session_state.rows = []

col1, col2 = st.columns([1, 1])
with col1:
    run = st.button("Đọc dữ liệu từ ảnh", type="primary", disabled=not uploaded_files)
with col2:
    clear = st.button("Xóa bảng hiện tại")

if clear:
    st.session_state.rows = []
    st.rerun()

if run:
    if not api_key:
        st.error("Bạn cần nhập OpenAI API key ở thanh bên trái để app đọc ảnh tự động.")
    else:
        progress = st.progress(0)
        for i, file in enumerate(uploaded_files, start=1):
            with st.spinner(f"Đang đọc ảnh {i}/{len(uploaded_files)}: {file.name}"):
                try:
                    data_url = image_to_data_url(file)
                    row = call_openai(api_key, data_url, extra_note)
                    st.session_state.rows.append(row)
                    st.success(f"Đã đọc: {file.name}")
                except Exception as e:
                    st.error(f"Lỗi khi đọc {file.name}: {e}")
            progress.progress(i / len(uploaded_files))

if uploaded_files:
    with st.expander("Xem ảnh đã chọn", expanded=False):
        cols = st.columns(min(3, len(uploaded_files)))
        for idx, file in enumerate(uploaded_files):
            with cols[idx % len(cols)]:
                try:
                    img = Image.open(io.BytesIO(file.getvalue()))
                    st.image(img, caption=file.name, use_container_width=True)
                except Exception:
                    st.write(file.name)

st.subheader("Bảng dữ liệu")
if st.session_state.rows:
    df = pd.DataFrame(st.session_state.rows, columns=FIELDS)
else:
    df = pd.DataFrame([{field: "" for field in FIELDS}], columns=FIELDS)

edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "SL": st.column_config.NumberColumn("SL", min_value=0, step=1),
    },
)
st.session_state.rows = edited_df.to_dict("records")

csv_bytes = make_csv_bytes(edited_df)
filename = "du_lieu_don_hang_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
st.download_button("Tải file CSV", data=csv_bytes, file_name=filename, mime="text/csv")

st.subheader("Copy nhanh để dán vào Google Sheet")
tsv = edited_df.to_csv(index=False, sep="\t")
st.text_area("Copy toàn bộ nội dung bên dưới", value=tsv, height=160)
