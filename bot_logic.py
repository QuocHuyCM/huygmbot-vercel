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


# ==================== BIẾN TOÀN CỤC (trạng thái trong bộ nhớ) ====================
# Lưu ý: trên serverless, các biến này KHÔNG đảm bảo giữ nguyên giữa các lần
# gọi (cold start sẽ reset về rỗng). check_bio_enabled do đó luôn đọc lại
# từ DB nếu không có trong cache, xem check_bio_khi_chat().
warn_count = {}
check_bio_enabled = {}
bio_check_cache = {}
BIO_CACHE_SECONDS = 300


# ==================== HELPER ====================
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
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        uid = user.id
        mention = get_mention(user)
        warn_count[uid] = warn_count.get(uid, 0) + 1
        count = warn_count[uid]
        if count >= 3:
            await context.bot.ban_chat_member(update.message.chat_id, uid)
            await update.message.reply_text(f"🚫 {mention} đã bị ban sau 3 lần cảnh báo!", parse_mode="HTML")
            warn_count[uid] = 0
        else:
            await update.message.reply_text(f"⚠️ {mention} bị cảnh báo lần {count}/3!", parse_mode="HTML")
    else:
        await update.message.reply_text("Reply vào tin nhắn người cần cảnh báo!")


async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        mention = get_mention(user)
        warn_count[user.id] = 0
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
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True
            )
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
    until_date_bio = datetime.datetime.now() + datetime.timedelta(days=7)
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
        f"⚠️ {mention} đã bị mute tự động <b>7 ngày</b>!\n"
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
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True
                )
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
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_send_polls=True,
                    can_add_web_page_previews=True,
                    can_invite_users=True,
                )
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
def build_application() -> Application:
    app = Application.builder().token(TOKEN).build()

    app.add_error_handler(xu_ly_loi)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("unwarn", unwarn))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("kick", kick))

    # Federation
    app.add_handler(CommandHandler("fban", fban))
    app.add_handler(CommandHandler("funban", funban))
    app.add_handler(CommandHandler("fmute", fmute))
    app.add_handler(CommandHandler("funmute", funmute))
    app.add_handler(CommandHandler("scanadmin", scan_admin))

    # Tiện ích
    app.add_handler(CommandHandler("kiemtra", kiem_tra_db))
    app.add_handler(CommandHandler("dsmute", ds_mute))
    app.add_handler(CommandHandler("xoadsmute", xoa_khoi_dsmute))

    # Check bio
    app.add_handler(CommandHandler("checkbio", check_bio_thu_cong))
    app.add_handler(CommandHandler("batcheckbio", bat_check_bio))
    app.add_handler(CommandHandler("tatcheckbio", tat_check_bio))
    app.add_handler(CommandHandler("uncheckbio", uncheck_bio))
    app.add_handler(CommandHandler("unmutebio", unmute_bio))

    # Chào mừng / tạm biệt
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, chao_mung))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, tam_biet))

    # Group 0: check bio khi có tin nhắn text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_bio_khi_chat), group=0)

    # Group 2: lưu nhóm + user (mọi loại tin nhắn)
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Sticker.ALL |
        filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE,
        xu_ly_moi_tin_nhan
    ), group=2)

    return app


async def process_update(update_data: dict):
    """Xử lý 1 update Telegram nhận qua webhook. Tạo Application mới,
    khởi tạo, xử lý, rồi đóng lại — an toàn trong 1 event loop duy nhất
    (tránh lỗi mixing event loop giữa các lần gọi serverless)."""
    app = build_application()
    async with app:
        update = Update.de_json(update_data, app.bot)
        await app.process_update(update)
