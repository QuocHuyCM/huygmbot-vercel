# HuyGMbot — Supabase + GitHub + Vercel

## Đã thay đổi so với bản gốc

**Đã bỏ** (theo yêu cầu — không cần lịch hẹn giờ và kiểm duyệt ảnh AI):
- Thông báo tự động định kỳ (`/batthongbao`, `/tatthongbao`...)
- Tự động xóa ảnh sau N phút (`/batxoaanh`, `/setxoaanh`...)
- Lịch xóa tin nhắn theo giờ (`/datgioxoa`, `/tatgioxoa`, `/xemgioxoa`)
- Kiểm duyệt ảnh/sticker 18+ bằng NudeNet

**Giữ nguyên toàn bộ:** mute/unmute, warn/ban/kick, check bio tự động + thủ công,
federation (fban/funban/fmute/funmute), scan admin, danh sách mute, kiểm tra DB.

**Đổi:** DB từ PostgreSQL trên Railway → Supabase Postgres. Bot chạy theo
kiểu **webhook** (Vercel) thay vì **polling** (Railway) — do Vercel không giữ
được tiến trình chạy nền.

## Các bước triển khai

### 1. Tạo bảng trong Supabase (chạy 1 lần, trên máy local)

Vào Supabase → **Project Settings → Database → Connection string** → chọn
tab **URI**, và nên dùng **Transaction pooler** (cổng 6543) vì phù hợp với
serverless (nhiều kết nối ngắn hạn cùng lúc).

```bash
cd telegram-bot-vercel
pip install psycopg2-binary
export DATABASE_URL="postgresql://postgres.xxxx:[PASSWORD]@aws-x-xx-xxxx-x.pooler.supabase.com:6543/postgres"
python setup_db.py
```

### 2. Đẩy code lên GitHub

```bash
git init
git add .
git commit -m "Chuyển sang Supabase + Vercel"
git remote add origin https://github.com/QuocHuyCM/<ten-repo>.git
git push -u origin main
```

Lưu ý: `.gitignore` đã chặn không đẩy `.env` lên — không commit token/mật khẩu.

### 3. Deploy trên Vercel

- vercel.com → **New Project** → Import repo GitHub vừa tạo.
- Vào **Settings → Environment Variables**, thêm:
  - `BOT_TOKEN` — token bot lấy từ BotFather (nhớ **revoke token cũ** trước, vì token cũ đã lộ trong code)
  - `DATABASE_URL` — connection string Supabase (giống bước 1)
  - `WEBHOOK_SECRET` — tuỳ chọn, một chuỗi bí mật tự đặt để Telegram xác thực webhook (khuyến nghị bật)
- Bấm **Deploy**.

### 4. Đăng ký webhook với Telegram

```bash
export BOT_TOKEN="token-moi-cua-ban"
export WEBHOOK_SECRET="chuoi-bi-mat-da-dat-o-buoc-3"   # nếu có dùng
python set_webhook.py https://ten-project.vercel.app/api/webhook
```

Kết quả trả về `{"ok": true, "result": true, ...}` là thành công.

### 5. Kiểm tra

Nhắn `/start` hoặc `/checkbio` trong nhóm có bot. Nếu không phản hồi, vào
Vercel → project → tab **Logs** để xem lỗi cụ thể.

## Việc cần làm thêm trên Telegram

Set quyền admin cho bot trong nhóm (mute/ban/xóa tin nhắn) như trước —
việc chuyển hạ tầng không ảnh hưởng quyền bot đã có trong nhóm.
