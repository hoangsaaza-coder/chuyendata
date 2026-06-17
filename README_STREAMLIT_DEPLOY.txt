HƯỚNG DẪN ĐƯA APP LÊN STREAMLIT COMMUNITY CLOUD

1) Tạo một repo GitHub mới, ví dụ: app-xuat-don-nem
2) Upload các file trong thư mục này lên repo:
   - app.py
   - requirements.txt
   - README_STREAMLIT_DEPLOY.txt

3) Vào https://share.streamlit.io hoặc Streamlit Community Cloud
4) Chọn New app
5) Chọn repo GitHub vừa tạo
6) Main file path: app.py
7) Trước khi Deploy, vào phần Advanced settings / Secrets và thêm:

OPENAI_API_KEY = "sk-..."

8) Bấm Deploy. Khi xong, Streamlit sẽ cấp link web để dùng online.

Lưu ý:
- Không commit API key lên GitHub.
- Nếu app lỗi thiếu thư viện, kiểm tra requirements.txt.
- App có thể upload nhiều ảnh, đọc thông tin, chỉnh lại bảng và tải CSV/copy vào Google Sheet.
