"""
Chạy trên máy local sau khi đã deploy lên Vercel, để báo cho Telegram gửi
update tới URL webhook của bạn.

Cách chạy:
    export BOT_TOKEN="..."
    export WEBHOOK_SECRET="chuoi-bi-mat-tuy-chon"   # phải khớp với biến trên Vercel, có thể bỏ qua
    python set_webhook.py https://ten-project.vercel.app/api/webhook
"""
import os
import sys
import httpx

if len(sys.argv) < 2:
    print("Dùng: python set_webhook.py https://ten-project.vercel.app/api/webhook")
    sys.exit(1)

url = sys.argv[1]
token = os.environ["BOT_TOKEN"]
secret = os.environ.get("WEBHOOK_SECRET")

params = {"url": url}
if secret:
    params["secret_token"] = secret

resp = httpx.get(f"https://api.telegram.org/bot{token}/setWebhook", params=params)
print(resp.status_code, resp.json())
