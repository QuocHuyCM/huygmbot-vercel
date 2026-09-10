import os
import datetime
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest, Forbidden

import psycopg2

# ==================== CẤU HÌNH (từ biến môi trường) ====================
TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

# ==================== DATABASE ====================
def get_conn():
    return psycopg2.connect(DATABASE_URL)


def save_setting(chat_id, key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO settings (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING", (str(chat_id),))
    c.execute(f"UPDATE settings SET {key} = %s WHERE chat_id = %s", (value, str(chat_id)))
    conn.commit()
    conn.close()


def get_setting(chat_id, key, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"SELECT {key} FROM settings WHERE chat_id = %s", (str(chat_id),))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else default


def get_all_groups():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT chat_id FROM groups")
    rows = c.fetchall()
    conn.close()
    return [int(row[0]) for row in rows]


def add_group(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO groups (chat_id) VALUES (%s) ON CONFLICT DO NOTHING", (str(chat_id),))
    conn.commit()
    conn.close()


def save_user(user_id, chat_id, username, first_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (user_id, chat_id, username, first_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, chat_id) DO UPDATE
        SET username = %s, first_name = %s
    """, (str(user_id), str(chat_id), username, first_name, username, first_name))
    conn.commit()
    conn.close()


def add_bio_whitelist(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO bio_whitelist (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (str(user_id),))
    conn.commit()
    conn.close()


def remove_bio_whitelist(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM bio_whitelist WHERE user_id = %s", (str(user_id),))
    conn.commit()
    conn.close()


def is_bio_whitelisted(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM bio_whitelist WHERE user_id = %s", (str(user_id),))
    row = c.fetchone()
    conn.close()
    return row is not None


def save_muted_user(user_id, chat_id, first_name, username, until_date, ly_do):
    conn = get_conn()
    c = conn.cursor()
    until_str = until_date.isoformat() if until_date else None
    muted_at = datetime.datetime.now().isoformat()
    c.execute("""
        INSERT INTO muted_users (user_id, chat_id, first_name, username, until_date, ly_do, muted_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, chat_id) DO UPDATE
        SET first_name = %s, username = %s, until_date = %s, ly_do = %s, muted_at = %s
    """, (str(user_id), str(chat_id), first_name, username, until_str, ly_do, muted_at,
          first_name, username, until_str, ly_do, muted_at))
    conn.commit()
    conn.close()


def remove_muted_user(user_id, chat_id=None):
    conn = get_conn()
    c = conn.cursor()
    if chat_id is not None:
        c.execute("DELETE FROM muted_users WHERE user_id = %s AND chat_id = %s", (str(user_id), str(chat_id)))
    else:
        c.execute("DELETE FROM muted_users WHERE user_id = %s", (str(user_id),))
    conn.commit()
    conn.close()


def get_muted_users(chat_id=None):
    conn = get_conn()
    c = conn.cursor()
    if chat_id is not None:
        c.execute("""SELECT user_id, chat_id, first_name, username, until_date, ly_do
                     FROM muted_users WHERE chat_id = %s""", (str(chat_id),))
    else:
        c.execute("""SELECT user_id, chat_id, first_name, username, until_date, ly_do
                     FROM muted_users""")
    rows = c.fetchall()
    conn.close()
    return rows


def get_user_id(username_or_id):
    conn = get_conn()
    c = conn.cursor()
    username = username_or_id.lstrip("@").lower()
    c.execute("SELECT user_id FROM users WHERE LOWER(username) = %s LIMIT 1", (username,))
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else None


# ---------- Danh sách chặn (từ cấm / sticker set cấm) ----------
def add_blocked_word(chat_id, word):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO blocked_words (chat_id, word) VALUES (%s, %s)
                 ON CONFLICT (chat_id, word) DO NOTHING""", (str(chat_id), word.lower()))
    conn.commit()
    conn.close()


def remove_blocked_word(chat_id, word):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM blocked_words WHERE chat_id = %s AND word = %s", (str(chat_id), word.lower()))
    conn.commit()
    conn.close()


def get_blocked_words(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT word FROM blocked_words WHERE chat_id = %s", (str(chat_id),))
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


def add_blocked_stickerset(chat_id, set_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO blocked_stickersets (chat_id, set_name) VALUES (%s, %s)
                 ON CONFLICT (chat_id, set_name) DO NOTHING""", (str(chat_id), set_name.lower()))
    conn.commit()
    conn.close()


def remove_blocked_stickerset(chat_id, set_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM blocked_stickersets WHERE chat_id = %s AND set_name = %s", (str(chat_id), set_name.lower()))
    conn.commit()
    conn.close()


def get_blocked_stickersets(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT set_name FROM blocked_stickersets WHERE chat_id = %s", (str(chat_id),))
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


# ---------- Trạng thái cảnh báo (warn) cho tính năng cấm chat leo thang ----------
def get_warn_state(user_id, chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT warn_count, ban_count FROM warn_state WHERE user_id = %s AND chat_id = %s",
              (str(user_id), str(chat_id)))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return 0, 0


def set_warn_state(user_id, chat_id, warn_count_val, ban_count_val):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO warn_state (user_id, chat_id, warn_count, ban_count)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, chat_id) DO UPDATE
        SET warn_count = %s, ban_count = %s
    """, (str(user_id), str(chat_id), warn_count_val, ban_count_val, warn_count_val, ban_count_val))
    conn.commit()
    conn.close()


def tinh_so_ngay_cam_chat(ban_count):
    """ban_count: lần thứ mấy bị cấm chat do warn đầy (1, 2, 3...).
    Quy tắc: lần 1=3 ngày, lần 2=5, lần 3=7, lần 4=10, sau đó mỗi lần +3 ngày."""
    bac_thang = [3, 5, 7, 10]
    if ban_count <= len(bac_thang):
        return bac_thang[ban_count - 1]
    return bac_thang[-1] + (ban_count - len(bac_thang)) * 3


# ==================== BIẾN TOÀN CỤC (trạng thái trong bộ nhớ) ====================
# Lưu ý: trên serverless, các biến này KHÔNG đảm bảo giữ nguyên giữa các lần
# gọi (cold start sẽ reset về rỗng). check_bio_enabled do đó luôn đọc lại
# từ DB nếu không có trong cache, xem check_bio_khi_chat().
warn_count = {}
check_bio_enabled = {}
bio_check_cache = {}
BIO_CACHE_SECONDS = 300


# ==================== HELPER ====================
def quyen_mo_day_du():
    """ChatPermissions đầy đủ để unmute — dùng thay cho tham số
    can_send_media_messages đã bị PTB 21+ loại bỏ, thay bằng khai riêng
    từng loại media."""
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
    )


def get_mention(user):
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.id}">{user.first_name}</a>'


# ==================== START ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot đang hoạt động!")


# ==================== CHÀO MỪNG ====================
async def chao_mung(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if not member.is_bot:
            save_user(member.id, update.message.chat_id, member.username or "", member.first_name or "")


async def tam_biet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.left_chat_member
    if user:
        mention = get_mention(user)
        await update.message.reply_text(f"👋 {mention} đã rời nhóm!", parse_mode="HTML")


# ==================== WARN / BAN / KICK / MUTE ====================
async def lay_muc_tieu_va_ly_do(update, context):
    """Xác định người bị nhắm tới + lý do từ 1 trong 2 cách dùng:
    - Reply vào tin nhắn + /lenh [lý do...]  → toàn bộ args là lý do
    - /lenh @username [lý do...] hoặc /lenh 123456789 [lý do...]
    Trả về (user_id, ten_hien_thi, ly_do) — ly_do có thể là None."""
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        ly_do = " ".join(context.args) if context.args else None
        return user.id, get_mention(user), ly_do

    if context.args:
        arg = context.args[0]
        ly_do = " ".join(context.args[1:]) if len(context.args) > 1 else None
        if arg.startswith("@") or not arg.lstrip("-").isdigit():
            uid = get_user_id(arg)
            if uid:
                return uid, arg, ly_do
            try:
                chat = await context.bot.get_chat(arg)
                uid = chat.id
                ten = f"@{chat.username}" if getattr(chat, "username", None) else (chat.first_name or arg)
                return uid, ten, ly_do
            except Exception:
                return None, None, None
        else:
            uid = int(arg)
            return uid, f'<a href="tg://user?id={uid}">{uid}</a>', ly_do

    return None, None, None


async def ap_dung_canh_bao(context, chat_id, uid, mention, ly_do):
    """Áp dụng 1 lần cảnh báo cho user: tăng đếm cảnh báo, nếu đủ giới hạn
    thì tự động cấm chat leo thang (dùng chung cho /warn và /lockurl).
    Trả về đoạn text (HTML) để gửi thông báo."""
    warn_limit = get_setting(chat_id, "warn_limit", 3)
    cur_warn, cur_ban = get_warn_state(uid, chat_id)
    cur_warn += 1

    if cur_warn >= warn_limit:
        cur_ban += 1
        so_ngay = tinh_so_ngay_cam_chat(cur_ban)
        until_date = datetime.datetime.now() + datetime.timedelta(days=so_ngay)
        ly_do_cam = f"Đầy {warn_limit} lần cảnh báo (lần cấm chat thứ {cur_ban})"
        if ly_do:
            ly_do_cam += f" — lần cuối: {ly_do}"
        try:
            await context.bot.restrict_chat_member(
                chat_id, uid,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            save_muted_user(uid, chat_id, "", "", until_date, ly_do_cam)
        except Exception:
            pass
        set_warn_state(uid, chat_id, 0, cur_ban)
        msg = (
            f"🚫 {mention} đã bị <b>cấm chat {so_ngay} ngày</b> sau khi đủ {warn_limit} lần cảnh báo!\n"
            f"📋 Đây là lần cấm chat thứ {cur_ban} của thành viên này."
        )
        if ly_do:
            msg += f"\n📝 Lý do lần này: {ly_do}"
    else:
        set_warn_state(uid, chat_id, cur_warn, cur_ban)
        msg = f"⚠️ {mention} bị cảnh báo lần {cur_warn}/{warn_limit}!"
        if ly_do:
            msg += f"\n📝 Lý do: {ly_do}"

    return msg


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, mention, ly_do = await lay_muc_tieu_va_ly_do(update, context)
    if not uid:
        await update.message.reply_text(
            "⚠️ Cách dùng:\n"
            "Reply vào tin nhắn + /warn [lý do]\n"
            "Hoặc: /warn @username lý do\n"
            "Hoặc: /warn 123456789 lý do"
        )
        return

    chat_id = update.message.chat_id
    msg = await ap_dung_canh_bao(context, chat_id, uid, mention, ly_do)
    await update.message.reply_text(msg, parse_mode="HTML")


async def setwarnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Cách dùng: /setwarnlimit 3  (số lần cảnh báo trước khi bị cấm chat)")
        return
    limit = int(context.args[0])
    if limit < 1:
        await update.message.reply_text("⚠️ Giới hạn phải từ 1 trở lên!")
        return
    save_setting(update.message.chat_id, "warn_limit", limit)
    await update.message.reply_text(f"✅ Đã đặt giới hạn cảnh báo: {limit} lần!")


async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        mention = get_mention(user)
        _, cur_ban = get_warn_state(user.id, update.message.chat_id)
        set_warn_state(user.id, update.message.chat_id, 0, cur_ban)
        await update.message.reply_text(f"✅ Đã xóa cảnh báo của {mention}!", parse_mode="HTML")
    else:
        await update.message.reply_text("Reply vào tin nhắn người cần xóa cảnh báo!")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        mention = get_mention(user)
        await context.bot.ban_chat_member(update.message.chat_id, user.id)
        await update.message.reply_text(f"🚫 {mention} đã bị ban!", parse_mode="HTML")
    else:
        await update.message.reply_text("Reply vào tin nhắn người cần ban!")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        mention = get_mention(user)
        await context.bot.unban_chat_member(update.message.chat_id, user.id)
        await update.message.reply_text(f"✅ {mention} đã được unban!", parse_mode="HTML")
    else:
        await update.message.reply_text("Reply vào tin nhắn người cần unban!")


async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        mention = get_mention(user)
        await context.bot.ban_chat_member(update.message.chat_id, user.id)
        await context.bot.unban_chat_member(update.message.chat_id, user.id)
        await update.message.reply_text(f"👢 {mention} đã bị kick!", parse_mode="HTML")
    else:
        await update.message.reply_text("Reply vào tin nhắn người cần kick!")


def parse_thoi_gian_va_ly_do(args):
    if not args:
        return None, None
    thoi_gian = None
    ly_do_start = 0
    arg0 = args[0].lower()
    try:
        if arg0.endswith("m") and arg0[:-1].isdigit():
            thoi_gian = int(arg0[:-1]) * 60
            ly_do_start = 1
        elif arg0.endswith("h") and arg0[:-1].isdigit():
            thoi_gian = int(arg0[:-1]) * 3600
            ly_do_start = 1
        elif arg0.endswith("d") and arg0[:-1].isdigit():
            thoi_gian = int(arg0[:-1]) * 86400
            ly_do_start = 1
        elif arg0.endswith("s") and arg0[:-1].isdigit():
            thoi_gian = int(arg0[:-1])
            ly_do_start = 1
    except Exception:
        pass
    ly_do = " ".join(args[ly_do_start:]) if len(args) > ly_do_start else None
    return thoi_gian, ly_do or None


def format_thoi_gian(giay):
    if giay >= 86400:
        return f"{giay // 86400} ngày"
    elif giay >= 3600:
        return f"{giay // 3600} giờ"
    elif giay >= 60:
        return f"{giay // 60} phút"
    return f"{giay} giây"


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Cách dùng (reply vào tin nhắn):\n"
            "/mute → mute vĩnh viễn\n"
            "/mute 30m → mute 30 phút\n"
            "/mute 1h spam → mute 1 giờ, lý do: spam"
        )
        return
    user = update.message.reply_to_message.from_user
    mention = get_mention(user)
    thoi_gian, ly_do = parse_thoi_gian_va_ly_do(context.args)
    until_date = None
    if thoi_gian:
        until_date = datetime.datetime.now() + datetime.timedelta(seconds=thoi_gian)
    await context.bot.restrict_chat_member(
        update.message.chat_id, user.id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=until_date
    )
    save_muted_user(user.id, update.message.chat_id, user.first_name or "", user.username or "", until_date, ly_do)
    if thoi_gian:
        msg = f"🔇 {mention} đã bị mute <b>{format_thoi_gian(thoi_gian)}</b>!"
    else:
        msg = f"🔇 {mention} đã bị mute <b>vĩnh viễn</b>!"
    if ly_do:
        msg += f"\n📋 Lý do: {ly_do}"
    await update.message.reply_text(msg, parse_mode="HTML")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        mention = get_mention(user)
        await context.bot.restrict_chat_member(
            update.message.chat_id, user.id,
            permissions=quyen_mo_day_du()
        )
        remove_muted_user(user.id, update.message.chat_id)
        await update.message.reply_text(f"✅ {mention} đã được unmute!", parse_mode="HTML")
    else:
        await update.message.reply_text("Reply vào tin nhắn người cần unmute!")


# ==================== CHECK BIO ====================
def co_link_trong_bio(bio: str) -> bool:
    if not bio:
        return False
    return "t.me/" in bio.lower()


async def bat_check_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    check_bio_enabled[chat_id] = True
    save_setting(chat_id, "check_bio", 1)
    await update.message.reply_text("✅ Đã bật kiểm tra bio (mute nếu bio có t.me/)!")


async def tat_check_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    check_bio_enabled[chat_id] = False
    save_setting(chat_id, "check_bio", 0)
    await update.message.reply_text("🔕 Đã tắt kiểm tra bio!")


async def lay_user_tu_lenh(update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        return user.id, get_mention(user)
    if context.args:
        arg = context.args[0]
        if arg.startswith("@") or not arg.lstrip("-").isdigit():
            uid = get_user_id(arg)
            if uid:
                return uid, arg
            try:
                chat = await context.bot.get_chat(arg)
                uid = chat.id
                ten = f"@{chat.username}" if getattr(chat, "username", None) else (chat.first_name or arg)
                return uid, ten
            except Exception:
                return None, None
        else:
            uid = int(arg)
            return uid, f'<a href="tg://user?id={uid}">{uid}</a>'
    return None, None


async def uncheck_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, ten = await lay_user_tu_lenh(update, context)
    if not uid:
        await update.message.reply_text(
            "⚠️ Không tìm thấy người dùng này!\n\n"
            "Cách dùng:\n"
            "Reply tin nhắn + /uncheckbio\n"
            "Hoặc: /uncheckbio @username\n"
            "Hoặc: /uncheckbio 123456789\n\n"
            "💡 Nếu @username không hoạt động, hãy reply trực tiếp vào tin nhắn của họ."
        )
        return
    add_bio_whitelist(uid)
    await update.message.reply_text(
        f"✅ Đã miễn trừ kiểm tra bio cho {ten} (áp dụng toàn bộ nhóm)!",
        parse_mode="HTML"
    )


async def check_bio_khi_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    msg = update.message
    user = msg.from_user
    chat_id = msg.chat_id

    if not user or user.is_bot:
        return
    if msg.chat.type not in ["group", "supergroup"]:
        return

    if chat_id not in check_bio_enabled:
        check_bio_enabled[chat_id] = bool(get_setting(chat_id, "check_bio", 1))
    if not check_bio_enabled.get(chat_id, True):
        return

    try:
        chat_member = await context.bot.get_chat_member(chat_id, user.id)
        if chat_member.status in ["administrator", "creator"]:
            return
    except Exception:
        return

    if is_bio_whitelisted(user.id):
        return

    now = datetime.datetime.now().timestamp()
    cache_key = f"{chat_id}:{user.id}"
    if cache_key in bio_check_cache:
        if now - bio_check_cache[cache_key] < BIO_CACHE_SECONDS:
            return
    bio_check_cache[cache_key] = now

    try:
        user_info = await context.bot.get_chat(user.id)
        bio = getattr(user_info, "bio", None) or ""
    except Exception:
        return

    if not co_link_trong_bio(bio):
        return

    mention = get_mention(user)
    until_date_bio = datetime.datetime.now() + datetime.timedelta(days=3)
    try:
        await context.bot.restrict_chat_member(
            chat_id, user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date_bio
        )
        save_muted_user(user.id, chat_id, user.first_name or "", user.username or "", until_date_bio, "Bio chứa link t.me/")
    except Exception:
        pass

    await context.bot.send_message(
        chat_id,
        f"⚠️ {mention} đã bị mute tự động <b>3 ngày</b>!\n"
        f"📋 Lý do: Bio chứa link.\n"
        f"🔗 Bio: <code>{bio[:200]}</code>\n"
        f"💡 Nếu bạn đã gỡ link ở Bio hãy ib admin để được mở mute ngay bây giờ!",
        parse_mode="HTML"
    )


async def check_bio_thu_cong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Reply vào tin nhắn người cần kiểm tra bio!")
        return
    user = update.message.reply_to_message.from_user
    mention = get_mention(user)
    try:
        user_info = await context.bot.get_chat(user.id)
        bio = getattr(user_info, "bio", None) or ""
    except Exception:
        await update.message.reply_text(f"⚠️ Không thể lấy thông tin của {mention}!", parse_mode="HTML")
        return

    da_go_mien_tru = False
    if is_bio_whitelisted(user.id):
        remove_bio_whitelist(user.id)
        da_go_mien_tru = True

    if bio:
        co_link = "✅ Có link" if co_link_trong_bio(bio) else "✔️ Không có link"
        text = f"👤 Bio của {mention}:\n<code>{bio}</code>\n\n🔍 Trạng thái: {co_link}"
    else:
        text = f"👤 {mention} không có bio."

    if da_go_mien_tru:
        text += "\n♻️ Đã gỡ miễn trừ, người này sẽ được kiểm tra bio trở lại."

    await update.message.reply_text(text, parse_mode="HTML")


async def unmute_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mở mute + miễn trừ check bio cùng lúc"""
    uid, ten = await lay_user_tu_lenh(update, context)
    if not uid:
        await update.message.reply_text(
            "⚠️ Không tìm thấy người dùng!\n\n"
            "Cách dùng:\n"
            "Reply tin nhắn + /unmutebio\n"
            "Hoặc: /unmutebio @username\n"
            "Hoặc: /unmutebio 123456789"
        )
        return

    groups = get_all_groups()
    thanh_cong = 0
    for cid in groups:
        try:
            await context.bot.restrict_chat_member(
                cid, uid,
                permissions=quyen_mo_day_du()
            )
            remove_muted_user(uid, cid)
            thanh_cong += 1
        except Exception:
            pass

    add_bio_whitelist(uid)

    await update.message.reply_text(
        f"✅ Đã mở mute {ten} ở {thanh_cong}/{len(groups)} nhóm!\n"
        f"🔓 Đã miễn trừ kiểm tra bio (sẽ không bị mute tự động nữa).",
        parse_mode="HTML"
    )


# ==================== FEDERATION ====================
async def fban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Reply vào tin nhắn người cần fban!")
        return
    user = update.message.reply_to_message.from_user
    mention = get_mention(user)
    groups = get_all_groups()
    thanh_cong = 0
    for cid in groups:
        try:
            await context.bot.ban_chat_member(cid, user.id)
            thanh_cong += 1
        except Exception:
            pass
    await update.message.reply_text(f"🚫 Đã ban {mention} khỏi {thanh_cong}/{len(groups)} nhóm!", parse_mode="HTML")


async def funban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Reply vào tin nhắn người cần funban!")
        return
    user = update.message.reply_to_message.from_user
    mention = get_mention(user)
    groups = get_all_groups()
    thanh_cong = 0
    for cid in groups:
        try:
            await context.bot.unban_chat_member(cid, user.id)
            thanh_cong += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ Đã unban {mention} khỏi {thanh_cong}/{len(groups)} nhóm!", parse_mode="HTML")


async def fmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = None
    user_name = "người dùng"
    thoi_gian_mute = None
    ly_do = None

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        user_id = user.id
        user_name = user.first_name
        thoi_gian_mute, ly_do = parse_thoi_gian_va_ly_do(context.args)
    elif context.args:
        arg = context.args[0]
        try:
            if arg.startswith("@") or not arg.lstrip("-").isdigit():
                user_id = get_user_id(arg)
                if not user_id:
                    try:
                        chat = await context.bot.get_chat(arg)
                        user_id = chat.id
                        user_name = getattr(chat, 'first_name', arg) or arg
                    except Exception:
                        await update.message.reply_text("⚠️ Không tìm thấy! Dùng ID số hoặc reply vào tin nhắn.")
                        return
            else:
                user_id = int(arg)
            thoi_gian_mute, ly_do = parse_thoi_gian_va_ly_do(context.args[1:])
        except Exception:
            await update.message.reply_text("⚠️ Không tìm thấy! Dùng ID số hoặc reply vào tin nhắn.")
            return

    if not user_id:
        await update.message.reply_text(
            "⚠️ Cách dùng:\n/fmute @username\n/fmute @username 30m\n/fmute @username 2h spam\nHoặc reply + /fmute 30m spam"
        )
        return

    until_date = None
    if thoi_gian_mute:
        until_date = datetime.datetime.now() + datetime.timedelta(seconds=thoi_gian_mute)

    groups = get_all_groups()
    thanh_cong = 0
    ds_nhom_mute = []
    for cid in groups:
        try:
            await context.bot.restrict_chat_member(
                cid, user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            save_muted_user(user_id, cid, user_name, "", until_date, ly_do)
            thanh_cong += 1
            try:
                chat_info = await context.bot.get_chat(cid)
                ten_nhom = chat_info.title or str(cid)
            except Exception:
                ten_nhom = str(cid)
            ds_nhom_mute.append((cid, ten_nhom))
        except Exception:
            pass

    mention = f'<a href="tg://user?id={user_id}">{user_name}</a>'
    if thoi_gian_mute:
        msg = f"🔇 Đã mute {mention} <b>{format_thoi_gian(thoi_gian_mute)}</b> ở {thanh_cong}/{len(groups)} nhóm!"
    else:
        msg = f"🔇 Đã mute vĩnh viễn {mention} ở {thanh_cong}/{len(groups)} nhóm!"
    if ly_do:
        msg += f"\n📋 Lý do: {ly_do}"

    if ds_nhom_mute:
        msg += "\n\n📋 Các nhóm đã mute:"
        for idx, (cid, ten_nhom) in enumerate(ds_nhom_mute, 1):
            msg += f"\n{idx}. {ten_nhom}"

    await update.message.reply_text(msg, parse_mode="HTML")


async def funmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = None
    user_name = "người dùng"

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        user_id = user.id
        user_name = user.first_name
    elif context.args:
        arg = context.args[0]
        try:
            if arg.startswith("@") or not arg.lstrip("-").isdigit():
                user_id = get_user_id(arg)
                if not user_id:
                    try:
                        chat = await context.bot.get_chat(arg)
                        user_id = chat.id
                        user_name = getattr(chat, 'first_name', arg) or arg
                    except Exception:
                        await update.message.reply_text("⚠️ Không tìm thấy! Dùng ID số hoặc reply vào tin nhắn.")
                        return
            else:
                user_id = int(arg)
        except Exception:
            await update.message.reply_text("⚠️ Không tìm thấy! Dùng ID số hoặc reply vào tin nhắn.")
            return

    if not user_id:
        await update.message.reply_text("⚠️ Dùng: /funmute @username hoặc reply vào tin nhắn!")
        return

    groups = get_all_groups()
    thanh_cong = 0
    for cid in groups:
        try:
            await context.bot.restrict_chat_member(
                cid, user_id,
                permissions=quyen_mo_day_du()
            )
            remove_muted_user(user_id, cid)
            thanh_cong += 1
        except Exception:
            pass

    mention = f'<a href="tg://user?id={user_id}">{user_name}</a>'
    await update.message.reply_text(f"✅ Đã unmute {mention} ở {thanh_cong}/{len(groups)} nhóm!", parse_mode="HTML")


async def scan_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        count = 0
        for admin in admins:
            user = admin.user
            if not user.is_bot:
                save_user(user.id, chat_id, user.username or "", user.first_name or "")
                count += 1
        add_group(chat_id)
        await update.message.reply_text(f"✅ Đã lưu nhóm và {count} admin!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi: {e}")


async def ds_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    rows = get_muted_users(chat_id)
    if not rows:
        await update.message.reply_text("✅ Hiện không có ai đang bị mute trong nhóm này!")
        return

    now = datetime.datetime.now()
    text = f"🔇 Danh sách bị mute ({len(rows)} người):\n\n"
    con_hieu_luc = 0

    for row in rows:
        uid, cid, first_name, username, until_str, ly_do = row
        ten = f"@{username}" if username else (first_name or "Không rõ")
        mention = f'<a href="tg://user?id={uid}">{ten}</a>'
        if until_str:
            try:
                until_dt = datetime.datetime.fromisoformat(until_str)
                if until_dt.tzinfo:
                    until_dt = until_dt.replace(tzinfo=None)
                if until_dt <= now:
                    remove_muted_user(uid, cid)
                    continue
                han = f"⏰ Hết hạn: {until_dt.strftime('%H:%M %d/%m/%Y')}"
            except Exception:
                han = "⏰ Không rõ thời hạn"
        else:
            han = "♾️ Vĩnh viễn"
        con_hieu_luc += 1
        text += f"{con_hieu_luc}. {mention} (ID: {uid})\n   {han}\n"
        if ly_do:
            text += f"   📋 Lý do: {ly_do}\n"
        text += "\n"

    if con_hieu_luc == 0:
        await update.message.reply_text("✅ Hiện không có ai đang bị mute trong nhóm này!")
        return

    await update.message.reply_text(text, parse_mode="HTML")


async def xoa_khoi_dsmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, ten = await lay_user_tu_lenh(update, context)
    if not uid:
        await update.message.reply_text("⚠️ Reply vào tin nhắn hoặc dùng /xoadsmute @username")
        return
    remove_muted_user(uid, update.message.chat_id)
    await update.message.reply_text(f"✅ Đã xóa {ten} khỏi danh sách mute!", parse_mode="HTML")


async def kiem_tra_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE chat_id = %s", (str(chat_id),))
        user_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM groups")
        group_count = c.fetchone()[0]
        c.execute("SELECT user_id, username, first_name FROM users WHERE chat_id = %s LIMIT 5", (str(chat_id),))
        users = c.fetchall()
        conn.close()
        text = f"📊 Database:\n👥 Nhóm lưu: {group_count}\n👤 User nhóm này: {user_count}\n\n5 user gần nhất:\n"
        for u in users:
            text += f"ID: {u[0]} | @{u[1]} | {u[2]}\n"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi: {e}")


# ==================== CLEAN SERVICE (bật/tắt tự xóa tin nhắn lệnh admin) ====================
async def cleanservice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not context.args or context.args[0].lower() not in ("on", "off", "yes", "no"):
        trang_thai = bool(get_setting(chat_id, "clean_service", 1))
        await update.message.reply_text(
            f"⚙️ Trạng thái hiện tại: {'BẬT ✅' if trang_thai else 'TẮT ❌'}\n"
            f"Cách dùng: /cleanservice on hoặc /cleanservice off"
        )
        return
    bat = context.args[0].lower() in ("on", "yes")
    save_setting(chat_id, "clean_service", 1 if bat else 0)
    # Không tự xóa tin nhắn lệnh này nếu vừa TẮT tính năng, để admin thấy phản hồi
    await update.message.reply_text(f"✅ Đã {'bật' if bat else 'tắt'} tự động xóa tin nhắn lệnh admin!")


# ==================== BLOCKLIST (từ cấm / bộ sticker cấm) ====================
async def blockadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    # Reply vào 1 sticker -> chặn cả bộ sticker đó
    if update.message.reply_to_message and update.message.reply_to_message.sticker:
        set_name = update.message.reply_to_message.sticker.set_name
        if not set_name:
            await update.message.reply_text("⚠️ Sticker này không thuộc bộ sticker nào để chặn.")
            return
        add_blocked_stickerset(chat_id, set_name)
        await update.message.reply_text(f"✅ Đã chặn bộ sticker: {set_name}")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Cách dùng:\n"
            "/addblocklist từ1 từ2 ... → chặn từ (tin nhắn chứa từ này sẽ bị xóa)\n"
            "Reply vào 1 sticker + /addblocklist → chặn cả bộ sticker đó"
        )
        return

    for tu in context.args:
        add_blocked_word(chat_id, tu)
    await update.message.reply_text(f"✅ Đã thêm {len(context.args)} từ vào danh sách cấm!")


async def blockdel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    if update.message.reply_to_message and update.message.reply_to_message.sticker:
        set_name = update.message.reply_to_message.sticker.set_name
        if set_name:
            remove_blocked_stickerset(chat_id, set_name)
            await update.message.reply_text(f"✅ Đã gỡ chặn bộ sticker: {set_name}")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Cách dùng: /blockdel từ1 từ2 ...")
        return

    for tu in context.args:
        remove_blocked_word(chat_id, tu)
    await update.message.reply_text(f"✅ Đã gỡ {len(context.args)} từ khỏi danh sách cấm!")


async def blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    words = get_blocked_words(chat_id)
    sets = get_blocked_stickersets(chat_id)
    text = "📋 Danh sách chặn của nhóm:\n\n"
    text += f"🔤 Từ cấm ({len(words)}): " + (", ".join(words) if words else "(trống)") + "\n\n"
    text += f"🎭 Bộ sticker cấm ({len(sets)}): " + (", ".join(sets) if sets else "(trống)")
    await update.message.reply_text(text)


# ==================== LỌC TỪ CẤM / STICKER CẤM ====================
async def loc_noi_dung_cam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    msg = update.message
    chat_id = msg.chat_id
    user = msg.from_user
    if not user or user.is_bot:
        return
    if msg.chat.type not in ["group", "supergroup"]:
        return

    # Không kiểm duyệt admin/creator
    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ["administrator", "creator"]:
            return
    except Exception:
        pass

    ly_do_xoa = None

    if msg.sticker and msg.sticker.set_name:
        blocked_sets = get_blocked_stickersets(chat_id)
        if msg.sticker.set_name.lower() in blocked_sets:
            ly_do_xoa = f"bộ sticker bị cấm ({msg.sticker.set_name})"

    if not ly_do_xoa and msg.text:
        blocked_words = get_blocked_words(chat_id)
        if blocked_words:
            noi_dung = msg.text.lower()
            for tu in blocked_words:
                if tu in noi_dung:
                    ly_do_xoa = f'từ bị cấm: "{tu}"'
                    break

    if ly_do_xoa:
        mention = get_mention(user)
        try:
            await msg.delete()
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id,
                f"🗑️ Tin nhắn của {mention} đã bị xóa vì chứa {ly_do_xoa}.",
                parse_mode="HTML"
            )
        except Exception:
            pass


# ==================== LOCKURL (cảnh báo nội dung bị khóa) ====================
def phat_hien_noi_dung_khoa(msg):
    """Trả về danh sách (tiếng Việt) các loại nội dung bị khóa mà tin nhắn
    này chứa, dùng cho /lockurl. Rỗng nếu không vi phạm gì."""
    ly_do = []
    text = msg.text or msg.caption or ""
    entities = list(msg.entities or []) + list(msg.caption_entities or [])

    co_link = False
    co_email = False
    co_phone = False
    co_command = False
    co_bot_mention = False

    for e in entities:
        if e.type in ("url", "text_link"):
            co_link = True
        elif e.type == "email":
            co_email = True
        elif e.type == "phone_number":
            co_phone = True
        elif e.type == "bot_command":
            co_command = True
        elif e.type == "mention":
            doan = text[e.offset:e.offset + e.length]
            if doan.lower().endswith("bot"):
                co_bot_mention = True
        elif e.type == "text_mention":
            if getattr(e.user, "is_bot", False):
                co_bot_mention = True

    if co_link:
        ly_do.append("link")
    if co_email:
        ly_do.append("email")
    if co_phone:
        ly_do.append("số điện thoại")
    if co_command:
        ly_do.append("lệnh (command)")
    if co_bot_mention:
        ly_do.append("nhắc tên bot khác")

    if getattr(msg, "location", None):
        ly_do.append("vị trí (location)")
    if getattr(msg, "venue", None):
        ly_do.append("địa điểm (venue)")
    if getattr(msg, "contact", None):
        ly_do.append("danh bạ (contact)")
    if getattr(msg, "forward_origin", None) or getattr(msg, "forward_date", None):
        ly_do.append("tin nhắn chuyển tiếp (forward)")
    if getattr(msg, "game", None):
        ly_do.append("game")
    if getattr(msg, "reply_markup", None):
        ly_do.append("nút bấm (button)")

    # Ký tự điều khiển RTL — thường dùng để ngụy trang link/từ cấm
    if text and any(ch in text for ch in ("\u202e", "\u202b", "\u200f", "\u061c")):
        ly_do.append("ký tự RTL bất thường")

    return ly_do


async def lockurl_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not context.args or context.args[0].lower() not in ("on", "off", "yes", "no"):
        trang_thai = bool(get_setting(chat_id, "lock_url", 0))
        await update.message.reply_text(
            f"⚙️ Trạng thái /lockurl hiện tại: {'BẬT ✅' if trang_thai else 'TẮT ❌'}\n"
            f"Cách dùng: /lockurl on hoặc /lockurl off\n\n"
            f"Khi bật, thành viên (không áp dụng cho admin) gửi link, sđt, địa chỉ, "
            f"location, contact, forward, email, command, button, hoặc nhắc tên bot khác "
            f"sẽ bị bot cảnh báo (áp dụng chung với giới hạn của /setwarnlimit)."
        )
        return
    bat = context.args[0].lower() in ("on", "yes")
    save_setting(chat_id, "lock_url", 1 if bat else 0)
    await update.message.reply_text(f"✅ Đã {'bật' if bat else 'tắt'} /lockurl!")


async def lockurl_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    msg = update.message
    chat_id = msg.chat_id
    user = msg.from_user
    if not user or user.is_bot:
        return
    if msg.chat.type not in ["group", "supergroup"]:
        return

    if not bool(get_setting(chat_id, "lock_url", 0)):
        return

    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ["administrator", "creator"]:
            return
    except Exception:
        pass

    danh_sach_vi_pham = phat_hien_noi_dung_khoa(msg)
    if not danh_sach_vi_pham:
        return

    mention = get_mention(user)
    ly_do = "Gửi nội dung bị khóa (/lockurl): " + ", ".join(danh_sach_vi_pham)
    canh_bao_msg = await ap_dung_canh_bao(context, chat_id, user.id, mention, ly_do)
    try:
        await context.bot.send_message(chat_id, canh_bao_msg, parse_mode="HTML")
    except Exception:
        pass


# ==================== HANDLER TỔNG - LƯU TIN NHẮN + NHÓM ====================
async def xu_ly_moi_tin_nhan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lưu nhóm + user vào DB cho mỗi tin nhắn trong group/supergroup."""
    if not update.message:
        return
    msg = update.message
    chat_id = msg.chat_id
    if msg.chat.type not in ["group", "supergroup"]:
        return
    add_group(chat_id)
    user = msg.from_user
    if user and not user.is_bot:
        save_user(user.id, chat_id, user.username or "", user.first_name or "")


async def xu_ly_loi(update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    if isinstance(error, (BadRequest, Forbidden)):
        return  # Im lặng, không crash
    import traceback
    print(f"Lỗi: {error}")
    traceback.print_exception(type(error), error, error.__traceback__)


# ==================== KHỞI TẠO APPLICATION ====================
def xoa_lenh_sau(func):
    """Bọc 1 command handler: chạy xong (đã gửi trả lời) rồi xóa tin nhắn
    lệnh gốc của người dùng, để nhóm gọn hơn — CHỈ khi /cleanservice đang bật
    (mặc định bật). Im lặng nếu bot không có quyền xóa tin."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        result = await func(update, context)
        try:
            chat_id = update.message.chat_id
            if bool(get_setting(chat_id, "clean_service", 1)):
                await update.message.delete()
        except Exception:
            pass
        return result
    return wrapper


def build_application() -> Application:
    app = Application.builder().token(TOKEN).build()

    app.add_error_handler(xu_ly_loi)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("unmute", xoa_lenh_sau(unmute)))
    app.add_handler(CommandHandler("mute", xoa_lenh_sau(mute)))
    app.add_handler(CommandHandler("warn", xoa_lenh_sau(warn)))
    app.add_handler(CommandHandler("unwarn", xoa_lenh_sau(unwarn)))
    app.add_handler(CommandHandler("ban", xoa_lenh_sau(ban)))
    app.add_handler(CommandHandler("unban", xoa_lenh_sau(unban)))
    app.add_handler(CommandHandler("kick", xoa_lenh_sau(kick)))

    # Federation
    app.add_handler(CommandHandler("fban", xoa_lenh_sau(fban)))
    app.add_handler(CommandHandler("funban", xoa_lenh_sau(funban)))
    app.add_handler(CommandHandler("fmute", xoa_lenh_sau(fmute)))
    app.add_handler(CommandHandler("funmute", xoa_lenh_sau(funmute)))
    app.add_handler(CommandHandler("scanadmin", xoa_lenh_sau(scan_admin)))

    # Tiện ích
    app.add_handler(CommandHandler("kiemtra", xoa_lenh_sau(kiem_tra_db)))
    app.add_handler(CommandHandler("dsmute", xoa_lenh_sau(ds_mute)))
    app.add_handler(CommandHandler("xoadsmute", xoa_lenh_sau(xoa_khoi_dsmute)))
    app.add_handler(CommandHandler("cleanservice", cleanservice))
    app.add_handler(CommandHandler("setwarnlimit", xoa_lenh_sau(setwarnlimit)))
    app.add_handler(CommandHandler("lockurl", lockurl_toggle))

    # Blocklist (từ cấm / sticker cấm)
    app.add_handler(CommandHandler("addblocklist", xoa_lenh_sau(blockadd)))
    app.add_handler(CommandHandler("blockdel", xoa_lenh_sau(blockdel)))
    app.add_handler(CommandHandler("blocklist", blocklist))

    # Check bio
    app.add_handler(CommandHandler("checkbio", xoa_lenh_sau(check_bio_thu_cong)))
    app.add_handler(CommandHandler("batcheckbio", xoa_lenh_sau(bat_check_bio)))
    app.add_handler(CommandHandler("tatcheckbio", xoa_lenh_sau(tat_check_bio)))
    app.add_handler(CommandHandler("uncheckbio", xoa_lenh_sau(uncheck_bio)))
    app.add_handler(CommandHandler("unmutebio", xoa_lenh_sau(unmute_bio)))

    # Chào mừng / tạm biệt
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, chao_mung))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, tam_biet))

    # Group 0: check bio khi có tin nhắn text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_bio_khi_chat), group=0)

    # Group 1: lọc từ cấm / sticker cấm
    app.add_handler(MessageHandler(
        (filters.TEXT & ~filters.COMMAND) | filters.Sticker.ALL,
        loc_noi_dung_cam
    ), group=1)

    # Group 2: /lockurl — kiểm tra link/sđt/location/contact/forward/email/command/button/bot
    # (Phải để RIÊNG nhóm khác với group 1: PTB chỉ chạy handler ĐẦU TIÊN khớp trong
    # cùng 1 group rồi dừng, nên nếu chung group với loc_noi_dung_cam thì lockurl_check
    # sẽ không bao giờ được gọi với tin nhắn text.)
    app.add_handler(MessageHandler(filters.ALL, lockurl_check), group=2)

    # Group 3: lưu nhóm + user (mọi loại tin nhắn)
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Sticker.ALL |
        filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE,
        xu_ly_moi_tin_nhan
    ), group=3)

    return app


async def process_update(update_data: dict):
    """Xử lý 1 update Telegram nhận qua webhook. Tạo Application mới,
    khởi tạo, xử lý, rồi đóng lại — an toàn trong 1 event loop duy nhất
    (tránh lỗi mixing event loop giữa các lần gọi serverless)."""
    app = build_application()
    async with app:
        update = Update.de_json(update_data, app.bot)
        await app.process_update(update)