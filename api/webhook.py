import os
import sys
import json
import asyncio
from http.server import BaseHTTPRequestHandler

# Cho phép import bot_logic.py ở thư mục gốc project
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from bot_logic import process_update  # noqa: E402

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")  # tuỳ chọn nhưng khuyến nghị


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Xác thực request thực sự đến từ Telegram (nếu đã cấu hình secret_token)
        if WEBHOOK_SECRET:
            incoming = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if incoming != WEBHOOK_SECRET:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Unauthorized")
                return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            update_data = json.loads(raw_body.decode("utf-8"))

            asyncio.run(process_update(update_data))

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            # Luôn trả 200 cho Telegram để nó không retry vô hạn; log lỗi ra console (Vercel Logs)
            print(f"[webhook] Lỗi xử lý update: {e}")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ERROR-LOGGED")

    def do_GET(self):
        # Endpoint kiểm tra sống (health check) — mở trình duyệt vào URL này sẽ thấy dòng chữ này
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot webhook is running.")
