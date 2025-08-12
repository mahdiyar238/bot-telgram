import os
import re
import tempfile
import logging
import requests
import instaloader
from yt_dlp import YoutubeDL
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import json
from datetime import datetime, timedelta
import shutil

TOKEN = "8380799753:AAE6y0Z4Dn1ca5B1bIlDlz699VhTMwDfiEQ"
MAX_FILESIZE = 50 * 1024 * 1024
YOUTUBE_API_KEY = ''
ADMIN_PASSWORD = "12345"

# توابع مدیریت آمار
def load_stats():
    """بارگذاری آمار از فایل"""
    if not os.path.exists("bot_stats.json"):
        return {
            "total_downloads": 0,
            "instagram_downloads": 0,
            "youtube_downloads": 0,
            "searches": 0,
            "daily_stats": {},
            "popular_features": {
                "instagram_download": 0,
                "youtube_download": 0,
                "instagram_search": 0,
                "youtube_search": 0,
                "profile_info": 0,
                "ai_chat": 0
            },
            "errors": [],
            "last_updated": ""
        }
    with open("bot_stats.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(stats):
    """ذخیره آمار در فایل"""
    stats["last_updated"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("bot_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=4)

def update_stats(feature_name):
    """به‌روزرسانی آمار استفاده"""
    stats = load_stats()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # آمار روزانه
    if today not in stats["daily_stats"]:
        stats["daily_stats"][today] = 0
    stats["daily_stats"][today] += 1
    
    # آمار کلی
    if feature_name in ["instagram", "youtube", "youtube_playlist"]:
        stats["total_downloads"] += 1
        if feature_name == "instagram":
            stats["instagram_downloads"] += 1
            stats["popular_features"]["instagram_download"] += 1
        else:
            stats["youtube_downloads"] += 1
            stats["popular_features"]["youtube_download"] += 1
    elif feature_name in ["search_instagram", "search_youtube"]:
        stats["searches"] += 1
        stats["popular_features"][feature_name] += 1
    elif feature_name in ["insta_profile", "youtube_channel"]:
        stats["popular_features"]["profile_info"] += 1
    elif feature_name == "ai_chat":
        stats["popular_features"]["ai_chat"] += 1
    
    save_stats(stats)

def log_error(error_msg, user_id=None):
    """ثبت خطا در لاگ"""
    stats = load_stats()
    error_entry = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "error": error_msg,
        "user_id": user_id
    }
    stats["errors"].append(error_entry)
    
    # نگه داشتن فقط 100 خطای آخر
    if len(stats["errors"]) > 100:
        stats["errors"] = stats["errors"][-100:]
    
    save_stats(stats)

# توابع مدیریت تنظیمات
def load_settings():
    """بارگذاری تنظیمات از فایل"""
    if not os.path.exists("bot_settings.json"):
        return {
            "admin_password": "12345",
            "max_file_size": 52428800,
            "features_enabled": {
                "instagram_download": True,
                "youtube_download": True,
                "instagram_search": True,
                "youtube_search": True,
                "profile_info": True,
                "ai_chat": True
            },
            "blocked_users": [],
            "broadcast_settings": {
                "last_broadcast": "",
                "total_sent": 0,
                "failed_sends": 0
            }
        }
    with open("bot_settings.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(settings):
    """ذخیره تنظیمات در فایل"""
    with open("bot_settings.json", "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def is_user_blocked(user_id):
    """بررسی مسدود بودن کاربر"""
    settings = load_settings()
    return user_id in settings["blocked_users"]

def is_feature_enabled(feature_name):
    """بررسی فعال بودن قابلیت"""
    settings = load_settings()
    return settings["features_enabled"].get(feature_name, True)

def get_youtube_subscribers_api(channel_id):
    if not YOUTUBE_API_KEY:
        return None
    url = f'https://www.googleapis.com/youtube/v3/channels?part=statistics&id={channel_id}&key={YOUTUBE_API_KEY}'
    try:
        response = requests.get(url)
        data = response.json()
        return data['items'][0]['statistics']['subscriberCount']
    except Exception:
        return None

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ======= تنظیمات AI Chat =======
TELEGRAM_BOT_TOKEN = "8380799753:AAE6y0Z4Dn1ca5B1bIlDlz699VhTMwDfiEQ"
API_KEY = "AIzaSyDa83raUrPJxcgUeMSCYcbCM2CoAiuDx4o"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

conversation_history = {}
USER_NAME = "لئو لوده"

def ask_ai(prompt: str, user_id: int):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    conversation_history[user_id].append({"role": "user", "content": prompt})
    
    system_prompt = f"شما یک دستیار دوست‌داشتنه و محترمانه فارسی هستید. نام کاربر شما '{USER_NAME}' هست. همیشه با احترام و خوش‌رویی پاسخ دهید و در صورت لزوم نام کاربر رو در پاسخ استفاده کنید."
    
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\nسوال {USER_NAME}: {prompt}"}]
        }]
    }
    
    response = requests.post(f"{API_URL}?key={API_KEY}", json=data, headers=headers)
    if response.status_code == 200:
        try:
            reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            conversation_history[user_id].append({"role": "assistant", "content": reply})
            return reply
        except Exception:
            return f"متأسفم {USER_NAME} عزیز، مشکلی پیش اومده. لطفاً دوباره امتحان کنید."
    return f"متأسفم {USER_NAME}، در حال حاضر نمی‌تونم پاسخ بدم. لطفاً بعداً دوباره امتحان کنید."

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔑 لطفاً رمز عبور مدیریت را وارد کنید:")
    context.user_data["admin_login"] = True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = {
        "id": user.id,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "username": user.username or ""
    }
    if not os.path.exists("users.json"):
        with open("users.json", "w", encoding="utf-8") as f:
            json.dump([], f)
    with open("users.json", "r", encoding="utf-8") as f:
        users = json.load(f)
    if not any(u["id"] == user.id for u in users):
        users.append(user_data)
        with open("users.json", "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
    member_count = len(users)
    keyboard = [
        [KeyboardButton("👤 اطلاعات کاربر"), KeyboardButton("📥 دانلود از اینستاگرام")],
        [KeyboardButton("📥 دانلود از یوتیوب"), KeyboardButton("📋 دانلود پلی‌لیست یوتیوب/Shorts")],
        [KeyboardButton("🔎 جستجوی اینستاگرام"), KeyboardButton("🔎 جستجوی یوتیوب")],
        [KeyboardButton("🔍 اطلاعات پیج اینستاگرام"), KeyboardButton("🔍 اطلاعات کانال یوتیوب")],
        [KeyboardButton("🤖 چت با هوش مصنوعی")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"👥 تعداد اعضای ربات: {member_count}\n\n✅ ثبت نام با موفقیت انجام شد!\n\n👇 یکی از گزینه‌های زیر را از منو انتخاب کنید:",
        reply_markup=reply_markup
    )
    context.user_data["mode"] = None

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
    
    user_id = update.effective_user.id
    reply_text = ask_ai(text, user_id)
    update_stats("ai_chat")
    await update.message.reply_text(reply_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()
    user = update.effective_user

    # ورود به پنل مدیریت
    if context.user_data.get("admin_login"):
        settings = load_settings()
        current_admin_password = settings.get("admin_password", ADMIN_PASSWORD)
        if message_text == current_admin_password:
            context.user_data["is_admin"] = True
            context.user_data["admin_login"] = False
            context.user_data["mode"] = "admin_panel"
            await show_admin_panel(update, context)
        else:
            context.user_data["is_admin"] = False
            context.user_data["admin_login"] = False
            await update.message.reply_text("❌ رمز اشتباه است.")
        return

    # چک کردن وجود فایل کاربران و ثبت نام کاربر
    if not os.path.exists("users.json"):
        await update.message.reply_text("⚠️ ابتدا باید ثبت نام کنید. لطفاً دستور /start را ارسال کنید.")
        return
    with open("users.json", "r", encoding="utf-8") as f:
        users = json.load(f)
    userinfo = next((u for u in users if u["id"] == user.id), None)
    if not userinfo:
        await update.message.reply_text("⚠️ ابتدا باید ثبت نام کنید. لطفاً دستور /start را ارسال کنید.")
        return
    
    # بررسی دکمه‌های منوی اصلی
    if message_text == "🤖 چت با هوش مصنوعی":
        context.user_data["mode"] = "ai_chat"
        await update.message.reply_text("🤖 سلام لئو لوده عزیز! من در خدمتم. هر سوالی دارید بپرسید:")
        return
    
    # پردازش بر اساس mode فعلی
    mode = context.user_data.get("mode")
    if mode == "ai_chat":
        await handle_ai_chat(update, context)
        return
    
    # بقیه کدهای پردازش منو (بدون تغییر)
    elif mode == "youtube_playlist":
        url = message_text
        await update.message.reply_text("⏳ در حال دانلود پلی‌لیست یا Shorts یوتیوب...")
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                files = download_youtube_playlist(url, temp_dir)
                update_stats("youtube_playlist")
                for file_path, title in files:
                    if os.path.getsize(file_path) >= MAX_FILESIZE:
                        await update.message.reply_text(f'❌ حجم فایل "{title}" بیشتر از 50MB است و قابل ارسال نیست.')
                        continue
                    with open(file_path, "rb") as f:
                        await update.message.reply_video(video=f, caption=title)
            except Exception as e:
                log_error(f"خطا در دانلود پلی‌لیست: {e}", user.id)
                await update.message.reply_text(f"❌ خطا در دانلود پلی‌لیست یا Shorts: {e}")
        return
    elif mode == "search_youtube":
        await update.message.reply_text("⏳ جستجو در یوتیوب...")
        try:
            results = search_youtube(message_text)
            update_stats("search_youtube")
            await update.message.reply_text("\n\n".join(results))
        except Exception as e:
            log_error(f"خطا در جستجوی یوتیوب: {e}", user.id)
            await update.message.reply_text(f"❌ خطا در جستجو: {e}")
        return
    elif mode == "search_instagram":
        await update.message.reply_text("⏳ جستجو در اینستاگرام...")
        try:
            results = search_instagram(message_text)
            update_stats("search_instagram")
            await update.message.reply_text("\n\n".join(results))
        except Exception as e:
            log_error(f"خطا در جستجوی اینستاگرام: {e}", user.id)
            await update.message.reply_text(f"❌ خطا در جستجو: {e}")
        return
    elif mode == "instagram":
        if "instagram.com" in message_text:
            if "/stories/" in message_text:
                m = re.search(r"/stories/([^/]+)/", message_text)
                if m:
                    username = m.group(1)
                    await update.message.reply_text("⏳ در حال دریافت استوری‌های پیج اینستاگرام...")
                    stories, error = download_instagram_stories(username)
                    if stories:
                        for story_url in stories:
                            try:
                                response = requests.get(story_url)
                                ext = story_url.split('.')[-1].split('?')[0]
                                fname = f"story.{ext}"
                                with open(fname, "wb") as f:
                                    f.write(response.content)
                                if ext in ["jpg", "jpeg", "png"]:
                                    with open(fname, "rb") as img_file:
                                        await update.message.reply_photo(photo=img_file)
                                else:
                                    with open(fname, "rb") as vid_file:
                                        await update.message.reply_video(video=vid_file)
                                os.remove(fname)
                            except Exception as e:
                                await update.message.reply_text(f"❌ خطا در ارسال استوری: {e}")
                    else:
                        await update.message.reply_text(f"❌ خطا: {error}")
                else:
                    await update.message.reply_text("⚠️ لینک استوری معتبر نیست!")
            else:
                await update.message.reply_text("⏳ در حال بررسی لینک اینستاگرام...")
                try:
                    img_urls, vid_urls, error = download_instagram_media(message_text)
                    sent = False
                    for img_url in img_urls:
                        try:
                            response = requests.get(img_url)
                            with open("insta.jpg", "wb") as f:
                                f.write(response.content)
                            if os.path.getsize("insta.jpg") >= MAX_FILESIZE:
                                os.remove("insta.jpg")
                                await update.message.reply_text('❌ حجم فایل بیشتر از 50MB است و قابل ارسال نیست.')
                                continue
                            with open("insta.jpg", "rb") as img_file:
                                await update.message.reply_photo(photo=img_file)
                            os.remove("insta.jpg")
                            sent = True
                        except Exception as e:
                            log_error(f"خطا در ارسال عکس اینستاگرام: {e}", user.id)
                            await update.message.reply_text(f"❌ خطا در ارسال عکس: {e}")
                    for vid_url in vid_urls:
                        try:
                            response = requests.get(vid_url)
                            with open("insta.mp4", "wb") as f:
                                f.write(response.content)
                            if os.path.getsize("insta.mp4") >= MAX_FILESIZE:
                                os.remove("insta.mp4")
                                await update.message.reply_text('❌ حجم فایل بیشتر از 50MB است و قابل ارسال نیست.')
                                continue
                            with open("insta.mp4", "rb") as vid_file:
                                await update.message.reply_video(video=vid_file)
                            os.remove("insta.mp4")
                            sent = True
                        except Exception as e:
                            log_error(f"خطا در ارسال ویدیو اینستاگرام: {e}", user.id)
                            await update.message.reply_text(f"❌ خطا در ارسال ویدیو: {e}")
                    if sent:
                        update_stats("instagram")
                    else:
                        log_error(f"خطا در دانلود اینستاگرام: {error}", user.id)
                        await update.message.reply_text(f"❌ خطا: {error}")
                except Exception as e:
                    log_error(f"خطا کلی در دانلود اینستاگرام: {e}", user.id)
                    await update.message.reply_text(f"❌ خطا در پردازش: {e}")
        elif re.match(r'^[A-Za-z0-9_.]+$', message_text):
            await update.message.reply_text("⏳ در حال دریافت استوری‌های پیج اینستاگرام...")
            stories, error = download_instagram_stories(message_text)
            if stories:
                for story_url in stories:
                    try:
                        response = requests.get(story_url)
                        ext = story_url.split('.')[-1].split('?')[0]
                        fname = f"story.{ext}"
                        with open(fname, "wb") as f:
                            f.write(response.content)
                        if ext in ["jpg", "jpeg", "png"]:
                            with open(fname, "rb") as img_file:
                                await update.message.reply_photo(photo=img_file)
                        else:
                            with open(fname, "rb") as vid_file:
                                await update.message.reply_video(video=vid_file)
                        os.remove(fname)
                    except Exception as e:
                        await update.message.reply_text(f"❌ خطا در ارسال استوری: {e}")
            else:
                await update.message.reply_text(f"❌ خطا: {error}")
        else:
            await update.message.reply_text("⚠️ لطفاً لینک پست یا آیدی پیج اینستاگرام را ارسال کنید!")
    elif mode == "youtube":
        if "youtube.com" not in message_text and "youtu.be" not in message_text:
            await update.message.reply_text("⚠️ لطفاً فقط لینک یوتیوب ارسال کنید!")
            return
        await update.message.reply_text("⏳ در حال دانلود ویدیو یوتیوب...")
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                file_path, title = download_youtube_video(message_text, temp_dir)
                file_size = os.path.getsize(file_path)
                if file_size >= MAX_FILESIZE:
                    await update.message.reply_text('❌ حجم فایل نهایی بیشتر از 50MB است و قابل ارسال نیست.')
                    return
                with open(file_path, "rb") as f:
                    await update.message.reply_video(video=f, caption=title)
                update_stats("youtube")
            except Exception as e:
                log_error(f"خطا در دانلود یوتیوب: {e}", user.id)
                logger.error(f"Error: {str(e)}", exc_info=True)
                await update.message.reply_text(f"❌ خطا در دانلود یا ارسال ویدیو: {e}")
    elif mode == "insta_profile":
        insta_id = message_text.strip()
        if not re.match(r'^[A-Za-z0-9_.]+$', insta_id):
            await update.message.reply_text("⚠️ لطفاً فقط آیدی معتبر اینستاگرام ارسال کنید!")
            return
        await update.message.reply_text("⏳ در حال دریافت اطلاعات پیج اینستاگرام...")
        try:
            info, profile_pic_url, error = get_instagram_profile_info(insta_id)
            if info:
                if profile_pic_url:
                    await update.message.reply_photo(photo=profile_pic_url)
                await update.message.reply_text(info)
                update_stats("insta_profile")
            else:
                log_error(f"خطا در دریافت اطلاعات پیج اینستاگرام: {error}", user.id)
                await update.message.reply_text(f"❌ خطا: {error}")
        except Exception as e:
            log_error(f"خطا کلی در دریافت اطلاعات پیج اینستاگرام: {e}", user.id)
            await update.message.reply_text(f"❌ خطا در پردازش: {e}")
    elif mode == "youtube_channel":
        channel_id_or_url = message_text.strip()
        await update.message.reply_text("⏳ در حال دریافت اطلاعات کانال یوتیوب...")
        try:
            info, profile_pic_url, error = get_youtube_channel_info(channel_id_or_url)
            if info:
                if profile_pic_url:
                    await update.message.reply_photo(photo=profile_pic_url)
                await update.message.reply_text(info)
                update_stats("youtube_channel")
            else:
                log_error(f"خطا در دریافت اطلاعات کانال یوتیوب: {error}", user.id)
                await update.message.reply_text(f"❌ خطا: {error}")
        except Exception as e:
            log_error(f"خطا کلی در دریافت اطلاعات کانال یوتیوب: {e}", user.id)
            await update.message.reply_text(f"❌ خطا در پردازش: {e}")
    else:
        await update.message.reply_text("👇 ابتدا یکی از گزینه‌های منو را انتخاب کنید.")

# توابع کمکی (بدون تغییر)
def extract_shortcode(url):
    match = re.search(r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", url)
    if match:
        return match.group(1)
    return None

def download_instagram_media(url):
    try:
        shortcode = extract_shortcode(url)
        if not shortcode:
            return [], [], "لینک معتبر نیست یا فرمتش اشتباه است."
        L = instaloader.Instaloader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        images = []
        videos = []
        if post.typename == "GraphImage":
            images.append(post.url)
        elif post.is_video:
            videos.append(post.video_url)
        elif post.typename == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                if node.is_video:
                    videos.append(node.video_url)
                else:
                    images.append(node.display_url)
            if not images and not videos:
                return [], [], "پست آلبوم خالی است."
        else:
            return [], [], "پست پشتیبانی نمی‌شود."
        return images, videos, None
    except Exception as e:
        return [], [], f"خطا: {e}"

def download_instagram_stories(username):
    try:
        L = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(L.context, username)
        stories = []
        for story in L.get_stories(userids=[profile.userid]):
            for item in story.get_items():
                if item.is_video:
                    stories.append(item.video_url)
                else:
                    stories.append(item.url)
        if not stories:
            return None, "هیچ استوری فعالی یافت نشد."
        return stories, None
    except Exception as e:
        return None, f"خطا: {e}"

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("👥 مدیریت کاربران"), KeyboardButton("📊 آمار و گزارش")],
        [KeyboardButton("📢 ارتباطات"), KeyboardButton("⚙️ تنظیمات")],
        [KeyboardButton("📁 مدیریت فایل‌ها"), KeyboardButton("🔍 نظارت")],
        [KeyboardButton("🔙 خروج از پنل مدیریت")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🎯 پنل مدیریت ربات - لطفاً یک گزینه را انتخاب کنید:", reply_markup=reply_markup)
    context.user_data["mode"] = "admin_panel"

async def show_user_management_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📋 لیست کاربران"), KeyboardButton("🔍 جستجوی کاربر")],
        [KeyboardButton("🚫 مسدود کردن کاربر"), KeyboardButton("✅ رفع مسدودیت")],
        [KeyboardButton("🗑️ حذف کاربر"), KeyboardButton("💬 پیام به کاربر")],
        [KeyboardButton("🔙 بازگشت به پنل اصلی")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("👥 پنل مدیریت کاربران:", reply_markup=reply_markup)
    context.user_data["mode"] = "user_management"

async def show_stats_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📊 آمار کلی"), KeyboardButton("📈 آمار استفاده")],
        [KeyboardButton("🔥 محبوب‌ترین قابلیت‌ها"), KeyboardButton("👤 کاربران فعال")],
        [KeyboardButton("📅 گزارش روزانه"), KeyboardButton("📆 گزارش هفتگی")],
        [KeyboardButton("🔙 بازگشت به پنل اصلی")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("📊 پنل آمار و گزارش:", reply_markup=reply_markup)
    context.user_data["mode"] = "stats_panel"

async def show_communication_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📢 پیام همگانی"), KeyboardButton("🚨 ارسال اعلان")],
        [KeyboardButton("📝 پیام به گروه خاص"), KeyboardButton("📊 آمار ارسال")],
        [KeyboardButton("🔙 بازگشت به پنل اصلی")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("📢 پنل ارتباطات:", reply_markup=reply_markup)
    context.user_data["mode"] = "communication_panel"

async def show_settings_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🔑 تغییر رمز ادمین"), KeyboardButton("🔧 تنظیمات ربات")],
        [KeyboardButton("📏 تنظیم حد دانلود"), KeyboardButton("🔄 فعال/غیرفعال قابلیت‌ها")],
        [KeyboardButton("💾 پشتیبان‌گیری"), KeyboardButton("🔄 بازیابی")],
        [KeyboardButton("🔙 بازگشت به پنل اصلی")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("⚙️ پنل تنظیمات:", reply_markup=reply_markup)
    context.user_data["mode"] = "settings_panel"

async def show_file_management_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🗑️ پاک کردن فایل‌های موقت"), KeyboardButton("📊 حجم فایل‌ها")],
        [KeyboardButton("📁 مشاهده فایل‌ها"), KeyboardButton("🧹 پاکسازی کامل")],
        [KeyboardButton("🔙 بازگشت به پنل اصلی")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("📁 پنل مدیریت فایل‌ها:", reply_markup=reply_markup)
    context.user_data["mode"] = "file_management"

async def show_monitoring_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📋 لاگ فعالیت‌ها"), KeyboardButton("❌ گزارش خطاها")],
        [KeyboardButton("🔍 نظارت لحظه‌ای"), KeyboardButton("📈 عملکرد سیستم")],
        [KeyboardButton("🔙 بازگشت به پنل اصلی")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🔍 پنل نظارت:", reply_markup=reply_markup)
    context.user_data["mode"] = "monitoring_panel"

async def show_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    if not os.path.exists("users.json"):
        await update.message.reply_text("❌ فایل کاربران یافت نشد!")
        return
    
    with open("users.json", "r", encoding="utf-8") as f:
        users = json.load(f)
    
    users_per_page = 5
    total_pages = (len(users) + users_per_page - 1) // users_per_page
    
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * users_per_page
    end_idx = min(start_idx + users_per_page, len(users))
    
    users_text = f"📋 لیست کاربران (صفحه {page + 1} از {total_pages}):\n\n"
    
    for i, user in enumerate(users[start_idx:end_idx], start_idx + 1):
        username = user.get('username', 'ندارد')
        users_text += f"{i}. 👤 {user['first_name']} {user.get('last_name', '')}\n"
        users_text += f"   🆔 آیدی: {user['id']}\n"
        users_text += f"   💬 یوزرنیم: @{username}\n\n"
    
    keyboard = []
    if page > 0:
        keyboard.append(KeyboardButton("⬅️ قبلی"))
    if page < total_pages - 1:
        keyboard.append(KeyboardButton("➡️ بعدی"))
    keyboard.append(KeyboardButton("🔙 بازگشت به پنل ادمین"))
    
    reply_markup = ReplyKeyboardMarkup([keyboard[i:i+2] for i in range(0, len(keyboard), 2)], resize_keyboard=True)
    await update.message.reply_text(users_text, reply_markup=reply_markup)
    
    context.user_data["current_page"] = page
    context.user_data["mode"] = "users_list"

# ===== اضافه کردن توابع مفقوده =====

def download_youtube_video(url, temp_dir):
    """دانلود ویدیو یوتیوب"""
    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'format': 'best[filesize<50M]/worst',
        'extractaudio': False,
        'audioformat': 'mp3',
        'embed_subs': True,
        'writesubtitles': False,
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get('title', 'unknown')
        ydl.download([url])
        
        # پیدا کردن فایل دانلود شده
        for file in os.listdir(temp_dir):
            if file.endswith(('.mp4', '.webm', '.mkv', '.flv')):
                return os.path.join(temp_dir, file), title
    
    raise Exception("فایل ویدیو یافت نشد")

def download_youtube_playlist(url, temp_dir):
    """دانلود پلی‌لیست یوتیوب"""
    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, '%(playlist_index)s - %(title)s.%(ext)s'),
        'format': 'best[filesize<50M]/worst',
        'extractaudio': False,
        'ignoreerrors': True,
    }
    
    files = []
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        # اگر پلی‌لیست است
        if 'entries' in info:
            for entry in info['entries'][:5]:  # محدود به 5 ویدیو
                if entry:
                    try:
                        ydl.download([entry['webpage_url']])
                        title = entry.get('title', 'unknown')
                        for file in os.listdir(temp_dir):
                            if title.replace('/', '_')[:20] in file and file.endswith(('.mp4', '.webm', '.mkv')):
                                files.append((os.path.join(temp_dir, file), title))
                                break
                    except:
                        continue
        else:
            # اگر ویدیو منفرد است
            ydl.download([url])
            title = info.get('title', 'unknown')
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv')):
                    files.append((os.path.join(temp_dir, file), title))
    
    return files

def search_youtube(query):
    """جستجو در یوتیوب"""
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
        }
        
        search_url = f"ytsearch5:{query}"
        
        with YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(search_url, download=False)
        
        results = []
        for entry in search_results['entries']:
            title = entry.get('title', 'نامشخص')
            url = entry.get('url', '')
            duration = entry.get('duration', 0)
            uploader = entry.get('uploader', 'نامشخص')
            
            # تبدیل مدت زمان به فرمت قابل خواندن
            if duration:
                minutes, seconds = divmod(duration, 60)
                duration_str = f"{minutes:02d}:{seconds:02d}"
            else:
                duration_str = "نامشخص"
            
            result_text = f"🎬 {title}\n👤 {uploader}\n⏱️ {duration_str}\n🔗 https://youtube.com/watch?v={url}"
            results.append(result_text)
        
        return results if results else ["❌ نتیجه‌ای یافت نشد!"]
    except Exception as e:
        return [f"❌ خطا در جستجو: {str(e)}"]

def search_instagram(query):
    """جستجو در اینستاگرام (شبیه‌سازی)"""
    try:
        # از آنجا که جستجوی واقعی اینستاگرام پیچیده است، 
        # فعلاً یک پیام راهنما برمی‌گردانیم
        results = [
            f"🔍 جستجو برای: {query}",
            "📝 برای جستجوی بهتر در اینستاگرام:",
            "• از هشتگ‌ها استفاده کنید (#example)",
            "• نام کاربری دقیق وارد کنید",
            "• از کلمات کلیدی مرتبط استفاده کنید",
            "",
            "💡 نکته: برای دسترسی کامل به محتوای اینستاگرام، لینک مستقیم پست را ارسال کنید."
        ]
        
        return results
    except Exception as e:
        return [f"❌ خطا در جستجو: {str(e)}"]

def get_instagram_profile_info(username):
    """دریافت اطلاعات پروفایل اینستاگرام"""
    try:
        L = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(L.context, username)
        
        followers_count = profile.followers
        following_count = profile.followees
        posts_count = profile.mediacount
        bio = profile.biography
        full_name = profile.full_name
        is_verified = profile.is_verified
        is_private = profile.is_private
        
        # فرمت کردن تعداد فالوورها
        if followers_count >= 1000000:
            followers_str = f"{followers_count/1000000:.1f}M"
        elif followers_count >= 1000:
            followers_str = f"{followers_count/1000:.1f}K"
        else:
            followers_str = str(followers_count)
        
        if following_count >= 1000000:
            following_str = f"{following_count/1000000:.1f}M"
        elif following_count >= 1000:
            following_str = f"{following_count/1000:.1f}K"
        else:
            following_str = str(following_count)
        
        verified_text = "✅" if is_verified else "❌"
        private_text = "🔒 خصوصی" if is_private else "🌐 عمومی"
        
        info_text = (
            f"🔍 اطلاعات پیج اینستاگرام:\n\n"
            f"👤 نام کاربری: @{username}\n"
            f"📛 نام کامل: {full_name}\n"
            f"✅ تأیید شده: {verified_text}\n"
            f"🔒 وضعیت: {private_text}\n"
            f"👥 فالوور: {followers_str}\n"
            f"➕ فالوینگ: {following_str}\n"
            f"📸 تعداد پست: {posts_count}\n"
            f"📝 بیوگرافی: {bio[:100] + '...' if len(bio) > 100 else bio}"
        )
        
        # URL عکس پروفایل
        profile_pic_url = profile.profile_pic_url
        
        return info_text, profile_pic_url, None
        
    except Exception as e:
        return None, None, f"خطا در دریافت اطلاعات: {str(e)}"

# ===== شروع تابع handle_message جدید =====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()
    user = update.effective_user

    # بررسی مسدود بودن کاربر
    if is_user_blocked(user.id):
        await update.message.reply_text("🚫 شما از استفاده از ربات محروم شده‌اید.")
        return

    # ورود به پنل مدیریت
    if context.user_data.get("admin_login"):
        settings = load_settings()
        current_admin_password = settings.get("admin_password", ADMIN_PASSWORD)
        if message_text == current_admin_password:
            context.user_data["is_admin"] = True
            context.user_data["admin_login"] = False
            context.user_data["mode"] = "admin_panel"
            await show_admin_panel(update, context)
        else:
            context.user_data["is_admin"] = False
            context.user_data["admin_login"] = False
            await update.message.reply_text("❌ رمز اشتباه است.")
        return

    # پردازش پنل مدیریت
    if context.user_data.get("is_admin"):
        
        if context.user_data.get("mode") == "admin_panel":
            if message_text == "🔙 خروج از پنل مدیریت":
                context.user_data["is_admin"] = False
                context.user_data["mode"] = None
                await start(update, context)
                return
            elif message_text == "👥 مدیریت کاربران":
                await show_user_management_panel(update, context)
                return
            elif message_text == "📊 آمار و گزارش":
                await show_stats_panel(update, context)
                return
            elif message_text == "📢 ارتباطات":
                await show_communication_panel(update, context)
                return
            elif message_text == "⚙️ تنظیمات":
                await show_settings_panel(update, context)
                return
            elif message_text == "📁 مدیریت فایل‌ها":
                await show_file_management_panel(update, context)
                return
            elif message_text == "🔍 نظارت":
                await show_monitoring_panel(update, context)
                return
        
        elif context.user_data.get("mode") == "user_management":
            if message_text == "📋 لیست کاربران":
                await show_users_list(update, context)
                return
            elif message_text == "🔍 جستجوی کاربر":
                context.user_data["mode"] = "search_user"
                await update.message.reply_text("🔍 لطفاً آیدی عددی کاربر مورد نظر را وارد کنید:")
                return
            elif message_text == "🚫 مسدود کردن کاربر":
                context.user_data["mode"] = "block_user"
                await update.message.reply_text("🚫 لطفاً آیدی عددی کاربر مورد نظر برای مسدود کردن را وارد کنید:")
                return
            elif message_text == "✅ رفع مسدودیت":
                context.user_data["mode"] = "unblock_user"
                await update.message.reply_text("✅ لطفاً آیدی عددی کاربر مورد نظر برای رفع مسدودیت را وارد کنید:")
                return
            elif message_text == "🗑️ حذف کاربر":
                context.user_data["mode"] = "delete_user"
                await update.message.reply_text("🗑️ لطفاً آیدی عددی کاربر مورد نظر برای حذف را وارد کنید:")
                return
            elif message_text == "💬 پیام به کاربر":
                context.user_data["mode"] = "message_user_id"
                await update.message.reply_text("💬 لطفاً آیدی عددی کاربر مورد نظر برای ارسال پیام را وارد کنید:")
                return
            elif message_text == "🔙 بازگشت به پنل اصلی":
                context.user_data["mode"] = "admin_panel"
                await show_admin_panel(update, context)
                return

        # پنل آمار و گزارش
        elif context.user_data.get("mode") == "stats_panel":
            if message_text == "📊 آمار کلی":
                if not os.path.exists("users.json"):
                    await update.message.reply_text("❌ فایل کاربران یافت نشد!")
                    return
                with open("users.json", "r", encoding="utf-8") as f:
                    users = json.load(f)
                stats_data = load_stats()
                stats = f"📊 آمار کلی ربات:\n\n👥 تعداد کل کاربران: {len(users)}\n📥 کل دانلودها: {stats_data['total_downloads']}\n📱 دانلود اینستاگرام: {stats_data['instagram_downloads']}\n🎬 دانلود یوتیوب: {stats_data['youtube_downloads']}\n🔍 جستجوها: {stats_data['searches']}\n🤖 وضعیت ربات: فعال\n📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                await update.message.reply_text(stats)
                return
            elif message_text == "📈 آمار استفاده":
                stats_data = load_stats()
                today = datetime.now().strftime('%Y-%m-%d')
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                
                today_usage = stats_data['daily_stats'].get(today, 0)
                yesterday_usage = stats_data['daily_stats'].get(yesterday, 0)
                
                usage_stats = f"📈 آمار استفاده:\n\n📅 امروز: {today_usage} استفاده\n📅 دیروز: {yesterday_usage} استفاده\n📊 آخرین به‌روزرسانی: {stats_data.get('last_updated', 'نامشخص')}"
                await update.message.reply_text(usage_stats)
                return
            elif message_text == "🔥 محبوب‌ترین قابلیت‌ها":
                stats_data = load_stats()
                popular = stats_data['popular_features']
                popular_text = "🔥 محبوب‌ترین قابلیت‌ها:\n\n"
                popular_text += f"📱 دانلود اینستاگرام: {popular['instagram_download']}\n"
                popular_text += f"🎬 دانلود یوتیوب: {popular['youtube_download']}\n"
                popular_text += f"🔍 جستجوی اینستاگرام: {popular['instagram_search']}\n"
                popular_text += f"🔍 جستجوی یوتیوب: {popular['youtube_search']}\n"
                popular_text += f"👤 اطلاعات پروفایل: {popular['profile_info']}"
                await update.message.reply_text(popular_text)
                return
            elif message_text == "👤 کاربران فعال":
                if not os.path.exists("users.json"):
                    await update.message.reply_text("❌ فایل کاربران یافت نشد!")
                    return
                with open("users.json", "r", encoding="utf-8") as f:
                    users = json.load(f)
                stats_data = load_stats()
                today = datetime.now().strftime('%Y-%m-%d')
                today_usage = stats_data['daily_stats'].get(today, 0)
                
                active_stats = f"👤 کاربران فعال:\n\n👥 کل کاربران: {len(users)}\n📊 استفاده امروز: {today_usage}\n📈 میانگین روزانه: {sum(stats_data['daily_stats'].values()) // max(len(stats_data['daily_stats']), 1)}"
                await update.message.reply_text(active_stats)
                return
            elif message_text == "📅 گزارش روزانه":
                stats_data = load_stats()
                today = datetime.now().strftime('%Y-%m-%d')
                today_usage = stats_data['daily_stats'].get(today, 0)
                
                daily_report = f"📅 گزارش روزانه ({today}):\n\n📊 استفاده امروز: {today_usage}\n📥 دانلودهای امروز: شامل در آمار کلی\n🔍 جستجوهای امروز: شامل در آمار کلی\n⏰ آخرین فعالیت: {stats_data.get('last_updated', 'نامشخص')}"
                await update.message.reply_text(daily_report)
                return
            elif message_text == "📆 گزارش هفتگی":
                stats_data = load_stats()
                weekly_usage = 0
                for i in range(7):
                    date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                    weekly_usage += stats_data['daily_stats'].get(date, 0)
                
                weekly_report = f"📆 گزارش هفتگی:\n\n📊 استفاده هفته گذشته: {weekly_usage}\n📈 میانگین روزانه: {weekly_usage // 7}\n📥 کل دانلودها: {stats_data['total_downloads']}\n🔍 کل جستجوها: {stats_data['searches']}"
                await update.message.reply_text(weekly_report)
                return
            elif message_text == "🔙 بازگشت به پنل اصلی":
                context.user_data["mode"] = "admin_panel"
                await show_admin_panel(update, context)
                return

        # پنل ارتباطات
        elif context.user_data.get("mode") == "communication_panel":
            if message_text == "📢 پیام همگانی":
                context.user_data["mode"] = "broadcast_message"
                await update.message.reply_text("📝 لطفاً متن پیام همگانی را وارد کنید:")
                return
            elif message_text == "🚨 ارسال اعلان":
                context.user_data["mode"] = "send_notification"
                await update.message.reply_text("🚨 لطفاً متن اعلان را وارد کنید:")
                return
            elif message_text == "📝 پیام به گروه خاص":
                await update.message.reply_text("🔧 این قابلیت در حال توسعه است.")
                return
            elif message_text == "📊 آمار ارسال":
                settings = load_settings()
                broadcast_stats = settings.get("broadcast_settings", {})
                stats_text = f"📊 آمار ارسال پیام‌ها:\n\n📅 آخرین ارسال: {broadcast_stats.get('last_broadcast', 'هیچ‌وقت')}\n✅ تعداد ارسال موفق: {broadcast_stats.get('total_sent', 0)}\n❌ تعداد ارسال ناموفق: {broadcast_stats.get('failed_sends', 0)}"
                await update.message.reply_text(stats_text)
                return
            elif message_text == "🔙 بازگشت به پنل اصلی":
                context.user_data["mode"] = "admin_panel"
                await show_admin_panel(update, context)
                return

        # پنل تنظیمات
        elif context.user_data.get("mode") == "settings_panel":
            if message_text == "🔑 تغییر رمز ادمین":
                context.user_data["mode"] = "change_admin_password"
                await update.message.reply_text("🔑 لطفاً رمز جدید ادمین را وارد کنید:")
                return
            elif message_text == "🔧 تنظیمات ربات":
                settings = load_settings()
                settings_text = f"🔧 تنظیمات فعلی ربات:\n\n📏 حداکثر حجم فایل: {settings['max_file_size'] // (1024*1024)} MB\n🔐 رمز ادمین: {'تنظیم شده' if settings['admin_password'] else 'تنظیم نشده'}\n👥 کاربران مسدود: {len(settings['blocked_users'])}"
                await update.message.reply_text(settings_text)
                return
            elif message_text == "📏 تنظیم حد دانلود":
                context.user_data["mode"] = "set_download_limit"
                await update.message.reply_text("📏 لطفاً حداکثر حجم فایل را به مگابایت وارد کنید (مثال: 50):")
                return
            elif message_text == "🔄 فعال/غیرفعال قابلیت‌ها":
                settings = load_settings()
                features = settings["features_enabled"]
                features_text = "🔄 وضعیت قابلیت‌ها:\n\n"
                features_text += f"📱 دانلود اینستاگرام: {'✅ فعال' if features['instagram_download'] else '❌ غیرفعال'}\n"
                features_text += f"🎬 دانلود یوتیوب: {'✅ فعال' if features['youtube_download'] else '❌ غیرفعال'}\n"
                features_text += f"🔍 جستجوی اینستاگرام: {'✅ فعال' if features['instagram_search'] else '❌ غیرفعال'}\n"
                features_text += f"🔍 جستجوی یوتیوب: {'✅ فعال' if features['youtube_search'] else '❌ غیرفعال'}\n"
                features_text += f"👤 اطلاعات پروفایل: {'✅ فعال' if features['profile_info'] else '❌ غیرفعال'}"
                await update.message.reply_text(features_text)
                return
            elif message_text == "💾 پشتیبان‌گیری":
                try:
                    import shutil
                    import datetime
                    backup_name = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy("users.json", f"{backup_name}_users.json")
                    shutil.copy("bot_stats.json", f"{backup_name}_stats.json")
                    shutil.copy("bot_settings.json", f"{backup_name}_settings.json")
                    await update.message.reply_text(f"✅ پشتیبان‌گیری با موفقیت انجام شد!\n📁 نام فایل‌ها: {backup_name}_*")
                except Exception as e:
                    await update.message.reply_text(f"❌ خطا در پشتیبان‌گیری: {e}")
                return
            elif message_text == "🔄 بازیابی":
                await update.message.reply_text("🔧 این قابلیت در حال توسعه است.")
                return
            elif message_text == "🔙 بازگشت به پنل اصلی":
                context.user_data["mode"] = "admin_panel"
                await show_admin_panel(update, context)
                return

        # پنل مدیریت فایل‌ها
        elif context.user_data.get("mode") == "file_management":
            if message_text == "🗑️ پاک کردن فایل‌های موقت":
                try:
                    temp_files = ["insta.jpg", "insta.mp4", "story.jpg", "story.mp4", "story.png"]
                    deleted_count = 0
                    for file in temp_files:
                        if os.path.exists(file):
                            os.remove(file)
                            deleted_count += 1
                    await update.message.reply_text(f"🗑️ {deleted_count} فایل موقت پاک شد.")
                except Exception as e:
                    await update.message.reply_text(f"❌ خطا در پاک کردن فایل‌ها: {e}")
                return
            elif message_text == "📊 حجم فایل‌ها":
                try:
                    total_size = 0
                    file_info = []
                    important_files = ["users.json", "bot_stats.json", "bot_settings.json"]
                    for file in important_files:
                        if os.path.exists(file):
                            size = os.path.getsize(file)
                            total_size += size
                            file_info.append(f"📄 {file}: {size // 1024} KB")
                    
                    size_text = f"📊 حجم فایل‌های مهم:\n\n" + "\n".join(file_info)
                    size_text += f"\n\n📦 مجموع: {total_size // 1024} KB"
                    await update.message.reply_text(size_text)
                except Exception as e:
                    await update.message.reply_text(f"❌ خطا در محاسبه حجم: {e}")
                return
            elif message_text == "📁 مشاهده فایل‌ها":
                try:
                    files = os.listdir(".")
                    bot_files = [f for f in files if f.endswith(('.json', '.py', '.log'))]
                    files_text = "📁 فایل‌های ربات:\n\n" + "\n".join([f"📄 {f}" for f in bot_files[:20]])
                    if len(bot_files) > 20:
                        files_text += f"\n\n... و {len(bot_files) - 20} فایل دیگر"
                    await update.message.reply_text(files_text)
                except Exception as e:
                    await update.message.reply_text(f"❌ خطا در مشاهده فایل‌ها: {e}")
                return
            elif message_text == "🧹 پاکسازی کامل":
                await update.message.reply_text("⚠️ این عملیات تمام فایل‌های موقت را پاک می‌کند.\n\n🔧 این قابلیت در حال توسعه است.")
                return
            elif message_text == "🔙 بازگشت به پنل اصلی":
                context.user_data["mode"] = "admin_panel"
                await show_admin_panel(update, context)
                return

        # پنل نظارت
        elif context.user_data.get("mode") == "monitoring_panel":
            if message_text == "📋 لاگ فعالیت‌ها":
                stats = load_stats()
                recent_activities = f"📋 آخرین فعالیت‌ها:\n\n📅 آخرین به‌روزرسانی: {stats.get('last_updated', 'نامشخص')}\n📊 استفاده امروز: {stats['daily_stats'].get(datetime.now().strftime('%Y-%m-%d'), 0)}\n📥 کل دانلودها: {stats['total_downloads']}\n🔍 کل جستجوها: {stats['searches']}"
                await update.message.reply_text(recent_activities)
                return
            elif message_text == "❌ گزارش خطاها":
                stats = load_stats()
                errors = stats.get("errors", [])
                if not errors:
                    await update.message.reply_text("✅ هیچ خطایی ثبت نشده است.")
                    return
                
                error_text = f"❌ آخرین خطاها ({len(errors)} خطا):\n\n"
                for i, error in enumerate(errors[-5:], 1):  # نمایش 5 خطای آخر
                    error_text += f"{i}. 🕐 {error['timestamp']}\n"
                    error_text += f"   👤 کاربر: {error.get('user_id', 'نامشخص')}\n"
                    error_text += f"   ❌ خطا: {error['error'][:100]}...\n\n"
                await update.message.reply_text(error_text)
                return
            elif message_text == "🔍 نظارت لحظه‌ای":
                import psutil
                try:
                    cpu_percent = psutil.cpu_percent()
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('.')
                    
                    system_info = f"🔍 وضعیت سیستم:\n\n💻 CPU: {cpu_percent}%\n🧠 RAM: {memory.percent}%\n💾 دیسک: {disk.percent}%\n\n🤖 وضعیت ربات: فعال"
                    await update.message.reply_text(system_info)
                except:
                    await update.message.reply_text("🔍 نظارت لحظه‌ای:\n\n🤖 وضعیت ربات: فعال\n📊 سیستم: در حال کار")
                return
            elif message_text == "📈 عملکرد سیستم":
                stats = load_stats()
                today = datetime.now().strftime('%Y-%m-%d')
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                
                performance = f"📈 عملکرد سیستم:\n\n📅 امروز: {stats['daily_stats'].get(today, 0)} درخواست\n📅 دیروز: {stats['daily_stats'].get(yesterday, 0)} درخواست\n📊 میانگین: {sum(stats['daily_stats'].values()) // max(len(stats['daily_stats']), 1)} درخواست/روز\n⚡ وضعیت: {'عالی' if stats['daily_stats'].get(today, 0) > 10 else 'خوب'}"
                await update.message.reply_text(performance)
                return
            elif message_text == "🔙 بازگشت به پنل اصلی":
                context.user_data["mode"] = "admin_panel"
                await show_admin_panel(update, context)
                return
        
        # پردازش ورودی‌های خاص ادمین
        elif context.user_data.get("mode") == "broadcast_message":
            # ارسال پیام همگانی
            if not os.path.exists("users.json"):
                await update.message.reply_text("❌ فایل کاربران یافت نشد!")
                return
            
            with open("users.json", "r", encoding="utf-8") as f:
                users = json.load(f)
            
            broadcast_text = message_text
            sent_count = 0
            failed_count = 0
            
            await update.message.reply_text(f"📢 شروع ارسال پیام به {len(users)} کاربر...")
            
            for user_data in users:
                try:
                    await context.bot.send_message(chat_id=user_data['id'], text=f"📢 پیام همگانی:\n\n{broadcast_text}")
                    sent_count += 1
                except Exception as e:
                    failed_count += 1
                    log_error(f"خطا در ارسال پیام همگانی به {user_data['id']}: {e}")
            
            # به‌روزرسانی آمار ارسال
            settings = load_settings()
            settings["broadcast_settings"]["last_broadcast"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            settings["broadcast_settings"]["total_sent"] += sent_count
            settings["broadcast_settings"]["failed_sends"] += failed_count
            save_settings(settings)
            
            result_text = f"✅ ارسال پیام همگانی تکمیل شد!\n\n📊 نتایج:\n✅ ارسال موفق: {sent_count}\n❌ ارسال ناموفق: {failed_count}"
            await update.message.reply_text(result_text)
            
            context.user_data["mode"] = "communication_panel"
            await show_communication_panel(update, context)
            return

        elif context.user_data.get("mode") == "send_notification":
            # ارسال اعلان
            if not os.path.exists("users.json"):
                await update.message.reply_text("❌ فایل کاربران یافت نشد!")
                return
            
            with open("users.json", "r", encoding="utf-8") as f:
                users = json.load(f)
            
            notification_text = message_text
            sent_count = 0
            failed_count = 0
            
            await update.message.reply_text(f"🚨 شروع ارسال اعلان به {len(users)} کاربر...")
            
            for user_data in users:
                try:
                    await context.bot.send_message(chat_id=user_data['id'], text=f"🚨 اعلان مهم:\n\n{notification_text}")
                    sent_count += 1
                except Exception as e:
                    failed_count += 1
                    log_error(f"خطا در ارسال اعلان به {user_data['id']}: {e}")
            
            result_text = f"✅ ارسال اعلان تکمیل شد!\n\n📊 نتایج:\n✅ ارسال موفق: {sent_count}\n❌ ارسال ناموفق: {failed_count}"
            await update.message.reply_text(result_text)
            
            context.user_data["mode"] = "communication_panel"
            await show_communication_panel(update, context)
            return

        elif context.user_data.get("mode") == "change_admin_password":
            # تغییر رمز ادمین
            new_password = message_text.strip()
            if len(new_password) < 3:
                await update.message.reply_text("❌ رمز باید حداقل 3 کاراکتر باشد!")
                return
            
            settings = load_settings()
            settings["admin_password"] = new_password
            save_settings(settings)
            
            await update.message.reply_text("✅ رمز ادمین با موفقیت تغییر کرد!")
            context.user_data["mode"] = "settings_panel"
            await show_settings_panel(update, context)
            return

        elif context.user_data.get("mode") == "set_download_limit":
            # تنظیم حد دانلود
            try:
                limit_mb = int(message_text.strip())
                if limit_mb < 1 or limit_mb > 2000:
                    await update.message.reply_text("❌ حد دانلود باید بین 1 تا 2000 مگابایت باشد!")
                    return
                
                settings = load_settings()
                settings["max_file_size"] = limit_mb * 1024 * 1024
                save_settings(settings)
                
                global MAX_FILESIZE
                MAX_FILESIZE = limit_mb * 1024 * 1024
                
                await update.message.reply_text(f"✅ حداکثر حجم فایل به {limit_mb} مگابایت تنظیم شد!")
                context.user_data["mode"] = "settings_panel"
                await show_settings_panel(update, context)
                return
            except ValueError:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
                return

        # پردازش ورودی‌های مدیریت کاربران
        elif context.user_data.get("mode") == "search_user":
            # جستجوی کاربر
            try:
                user_id = int(message_text.strip())
                if not os.path.exists("users.json"):
                    await update.message.reply_text("❌ فایل کاربران یافت نشد!")
                    return
                
                with open("users.json", "r", encoding="utf-8") as f:
                    users = json.load(f)
                
                found_user = next((u for u in users if u["id"] == user_id), None)
                if found_user:
                    username = found_user.get('username', 'ندارد')
                    user_info = f"👤 اطلاعات کاربر یافت شده:\n\n🆔 آیدی: {found_user['id']}\n👤 نام: {found_user['first_name']} {found_user.get('last_name', '')}\n💬 یوزرنیم: @{username}\n📅 تاریخ عضویت: موجود در سیستم"
                    await update.message.reply_text(user_info)
                else:
                    await update.message.reply_text("❌ کاربری با این آیدی یافت نشد!")
                
                context.user_data["mode"] = "user_management"
                await show_user_management_panel(update, context)
                return
            except ValueError:
                await update.message.reply_text("❌ لطفاً یک آیدی عددی معتبر وارد کنید!")
                return

        elif context.user_data.get("mode") == "block_user":
            # مسدود کردن کاربر
            try:
                user_id = int(message_text.strip())
                settings = load_settings()
                
                if user_id in settings["blocked_users"]:
                    await update.message.reply_text("⚠️ این کاربر قبلاً مسدود شده است!")
                else:
                    settings["blocked_users"].append(user_id)
                    save_settings(settings)
                    await update.message.reply_text(f"🚫 کاربر با آیدی {user_id} با موفقیت مسدود شد!")
                
                context.user_data["mode"] = "user_management"
                await show_user_management_panel(update, context)
                return
            except ValueError:
                await update.message.reply_text("❌ لطفاً یک آیدی عددی معتبر وارد کنید!")
                return

        elif context.user_data.get("mode") == "unblock_user":
            # رفع مسدودیت کاربر
            try:
                user_id = int(message_text.strip())
                settings = load_settings()
                
                if user_id not in settings["blocked_users"]:
                    await update.message.reply_text("⚠️ این کاربر مسدود نیست!")
                else:
                    settings["blocked_users"].remove(user_id)
                    save_settings(settings)
                    await update.message.reply_text(f"✅ مسدودیت کاربر با آیدی {user_id} برداشته شد!")
                
                context.user_data["mode"] = "user_management"
                await show_user_management_panel(update, context)
                return
            except ValueError:
                await update.message.reply_text("❌ لطفاً یک آیدی عددی معتبر وارد کنید!")
                return

        elif context.user_data.get("mode") == "delete_user":
            # حذف کاربر
            try:
                user_id = int(message_text.strip())
                if not os.path.exists("users.json"):
                    await update.message.reply_text("❌ فایل کاربران یافت نشد!")
                    return
                
                with open("users.json", "r", encoding="utf-8") as f:
                    users = json.load(f)
                
                user_to_delete = next((u for u in users if u["id"] == user_id), None)
                if user_to_delete:
                    users = [u for u in users if u["id"] != user_id]
                    with open("users.json", "w", encoding="utf-8") as f:
                        json.dump(users, f, ensure_ascii=False, indent=4)
                    await update.message.reply_text(f"🗑️ کاربر {user_to_delete['first_name']} با آیدی {user_id} از سیستم حذف شد!")
                else:
                    await update.message.reply_text("❌ کاربری با این آیدی یافت نشد!")
                
                context.user_data["mode"] = "user_management"
                await show_user_management_panel(update, context)
                return
            except ValueError:
                await update.message.reply_text("❌ لطفاً یک آیدی عددی معتبر وارد کنید!")
                return

        elif context.user_data.get("mode") == "message_user_id":
            # دریافت آیدی کاربر برای ارسال پیام
            try:
                user_id = int(message_text.strip())
                if not os.path.exists("users.json"):
                    await update.message.reply_text("❌ فایل کاربران یافت نشد!")
                    return
                
                with open("users.json", "r", encoding="utf-8") as f:
                    users = json.load(f)
                
                target_user = next((u for u in users if u["id"] == user_id), None)
                if target_user:
                    context.user_data["target_user_id"] = user_id
                    context.user_data["mode"] = "message_user_text"
                    await update.message.reply_text(f"💬 لطفاً متن پیام برای کاربر {target_user['first_name']} را وارد کنید:")
                else:
                    await update.message.reply_text("❌ کاربری با این آیدی یافت نشد!")
                    context.user_data["mode"] = "user_management"
                    await show_user_management_panel(update, context)
                return
            except ValueError:
                await update.message.reply_text("❌ لطفاً یک آیدی عددی معتبر وارد کنید!")
                return

        elif context.user_data.get("mode") == "message_user_text":
            # ارسال پیام به کاربر
            target_user_id = context.user_data.get("target_user_id")
            if target_user_id:
                try:
                    await context.bot.send_message(chat_id=target_user_id, text=f"💬 پیام از مدیر:\n\n{message_text}")
                    await update.message.reply_text(f"✅ پیام با موفقیت به کاربر {target_user_id} ارسال شد!")
                except Exception as e:
                    await update.message.reply_text(f"❌ خطا در ارسال پیام: {e}")
                
                context.user_data["target_user_id"] = None
                context.user_data["mode"] = "user_management"
                await show_user_management_panel(update, context)
                return

        # اگر ادمین است اما در حالت لیست کاربران است
        elif context.user_data.get("mode") == "users_list":
            if message_text == "⬅️ قبلی":
                current_page = context.user_data.get("current_page", 0)
                await show_users_list(update, context, current_page - 1)
                return
            elif message_text == "➡️ بعدی":
                current_page = context.user_data.get("current_page", 0)
                await show_users_list(update, context, current_page + 1)
                return
            elif message_text == "🔙 بازگشت به پنل ادمین":
                context.user_data["mode"] = "user_management"
                await show_user_management_panel(update, context)
                return

    # چک کردن وجود فایل کاربران و ثبت نام کاربر
    if not os.path.exists("users.json"):
        await update.message.reply_text("⚠️ ابتدا باید ثبت نام کنید. لطفاً دستور /start را ارسال کنید.")
        return
    with open("users.json", "r", encoding="utf-8") as f:
        users = json.load(f)
    userinfo = next((u for u in users if u["id"] == user.id), None)
    if not userinfo:
        await update.message.reply_text("⚠️ ابتدا باید ثبت نام کنید. لطفاً دستور /start را ارسال کنید.")
        return
    
    # بررسی دکمه‌های منوی اصلی
    if message_text == "👤 اطلاعات کاربر":
        context.user_data["mode"] = None
        admin_label = " (مدیر)" if context.user_data.get("is_admin") else ""
        await update.message.reply_text(
            f"👤 اطلاعات کاربری شما{admin_label}:\n\n🆔 آیدی: {userinfo['id']}\n🧑‍💼 نام: {userinfo['first_name']}\n🧑‍💼 نام خانوادگی: {userinfo['last_name']}\n💬 یوزرنیم: {userinfo['username']}"
        )
        return
    elif message_text == "📥 دانلود از اینستاگرام":
        context.user_data["mode"] = "instagram"
        await update.message.reply_text("📥 لطفاً لینک پست اینستاگرام را ارسال کنید:")
        return
    elif message_text == "📥 دانلود از یوتیوب":
        context.user_data["mode"] = "youtube"
        await update.message.reply_text("📥 لطفاً لینک ویدیوی یوتیوب را ارسال کنید:")
        return
    elif message_text == "📋 دانلود پلی‌لیست یوتیوب/Shorts":
        context.user_data["mode"] = "youtube_playlist"
        await update.message.reply_text("📋 لطفاً لینک پلی‌لیست یا Shorts یوتیوب را ارسال کنید:")
        return
    elif message_text == "🔎 جستجوی اینستاگرام":
        context.user_data["mode"] = "search_instagram"
        await update.message.reply_text("🔎 لطفاً کلمه کلیدی جستجو برای اینستاگرام را وارد کنید:")
        return
    elif message_text == "🔎 جستجوی یوتیوب":
        context.user_data["mode"] = "search_youtube"
        await update.message.reply_text("🔎 لطفاً کلمه کلیدی جستجو برای یوتیوب را وارد کنید:")
        return
    elif message_text == "🔍 اطلاعات پیج اینستاگرام":
        context.user_data["mode"] = "insta_profile"
        await update.message.reply_text("🔍 لطفاً آیدی پیج اینستاگرام را ارسال کنید:")
        return
    elif message_text == "🔍 اطلاعات کانال یوتیوب":
        context.user_data["mode"] = "youtube_channel"
        await update.message.reply_text("🔍 لطفاً آیدی یا لینک کانال یوتیوب را ارسال کنید:")
        return
    
    # پردازش بر اساس mode فعلی
    mode = context.user_data.get("mode")
    if mode == "youtube_playlist":
        url = message_text
        await update.message.reply_text("⏳ در حال دانلود پلی‌لیست یا Shorts یوتیوب...")
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                files = download_youtube_playlist(url, temp_dir)
                update_stats("youtube_playlist")  # ثبت آمار
                for file_path, title in files:
                    if os.path.getsize(file_path) >= MAX_FILESIZE:
                        await update.message.reply_text(f'❌ حجم فایل "{title}" بیشتر از 50MB است و قابل ارسال نیست.')
                        continue
                    with open(file_path, "rb") as f:
                        await update.message.reply_video(video=f, caption=title)
            except Exception as e:
                log_error(f"خطا در دانلود پلی‌لیست: {e}", user.id)
                await update.message.reply_text(f"❌ خطا در دانلود پلی‌لیست یا Shorts: {e}")
        return
    elif mode == "search_youtube":
        await update.message.reply_text("⏳ جستجو در یوتیوب...")
        try:
            results = search_youtube(message_text)
            update_stats("search_youtube")  # ثبت آمار
            await update.message.reply_text("\n\n".join(results))
        except Exception as e:
            log_error(f"خطا در جستجوی یوتیوب: {e}", user.id)
            await update.message.reply_text(f"❌ خطا در جستجو: {e}")
        return
    elif mode == "search_instagram":
        await update.message.reply_text("⏳ جستجو در اینستاگرام...")
        try:
            results = search_instagram(message_text)
            update_stats("search_instagram")  # ثبت آمار
            await update.message.reply_text("\n\n".join(results))
        except Exception as e:
            log_error(f"خطا در جستجوی اینستاگرام: {e}", user.id)
            await update.message.reply_text(f"❌ خطا در جستجو: {e}")
        return
    elif mode == "instagram":
        if "instagram.com" in message_text:
            if "/stories/" in message_text:
                m = re.search(r"/stories/([^/]+)/", message_text)
                if m:
                    username = m.group(1)
                    await update.message.reply_text("⏳ در حال دریافت استوری‌های پیج اینستاگرام...")
                    stories, error = download_instagram_stories(username)
                    if stories:
                        for story_url in stories:
                            try:
                                response = requests.get(story_url)
                                ext = story_url.split('.')[-1].split('?')[0]
                                fname = f"story.{ext}"
                                with open(fname, "wb") as f:
                                    f.write(response.content)
                                if ext in ["jpg", "jpeg", "png"]:
                                    with open(fname, "rb") as img_file:
                                        await update.message.reply_photo(photo=img_file)
                                else:
                                    with open(fname, "rb") as vid_file:
                                        await update.message.reply_video(video=vid_file)
                                os.remove(fname)
                            except Exception as e:
                                await update.message.reply_text(f"❌ خطا در ارسال استوری: {e}")
                    else:
                        await update.message.reply_text(f"❌ خطا: {error}")
                else:
                    await update.message.reply_text("⚠️ لینک استوری معتبر نیست!")
            else:
                await update.message.reply_text("⏳ در حال بررسی لینک اینستاگرام...")
                try:
                    img_urls, vid_urls, error = download_instagram_media(message_text)
                    sent = False
                    for img_url in img_urls:
                        try:
                            response = requests.get(img_url)
                            with open("insta.jpg", "wb") as f:
                                f.write(response.content)
                            if os.path.getsize("insta.jpg") >= MAX_FILESIZE:
                                os.remove("insta.jpg")
                                await update.message.reply_text('❌ حجم فایل بیشتر از 50MB است و قابل ارسال نیست.')
                                continue
                            with open("insta.jpg", "rb") as img_file:
                                await update.message.reply_photo(photo=img_file)
                            os.remove("insta.jpg")
                            sent = True
                        except Exception as e:
                            log_error(f"خطا در ارسال عکس اینستاگرام: {e}", user.id)
                            await update.message.reply_text(f"❌ خطا در ارسال عکس: {e}")
                    for vid_url in vid_urls:
                        try:
                            response = requests.get(vid_url)
                            with open("insta.mp4", "wb") as f:
                                f.write(response.content)
                            if os.path.getsize("insta.mp4") >= MAX_FILESIZE:
                                os.remove("insta.mp4")
                                await update.message.reply_text('❌ حجم فایل بیشتر از 50MB است و قابل ارسال نیست.')
                                continue
                            with open("insta.mp4", "rb") as vid_file:
                                await update.message.reply_video(video=vid_file)
                            os.remove("insta.mp4")
                            sent = True
                        except Exception as e:
                            log_error(f"خطا در ارسال ویدیو اینستاگرام: {e}", user.id)
                            await update.message.reply_text(f"❌ خطا در ارسال ویدیو: {e}")
                    if sent:
                        update_stats("instagram")  # ثبت آمار
                    else:
                        log_error(f"خطا در دانلود اینستاگرام: {error}", user.id)
                        await update.message.reply_text(f"❌ خطا: {error}")
                except Exception as e:
                    log_error(f"خطا کلی در دانلود اینستاگرام: {e}", user.id)
                    await update.message.reply_text(f"❌ خطا در پردازش: {e}")
        elif re.match(r'^[A-Za-z0-9_.]+$', message_text):
            await update.message.reply_text("⏳ در حال دریافت استوری‌های پیج اینستاگرام...")
            stories, error = download_instagram_stories(message_text)
            if stories:
                for story_url in stories:
                    try:
                        response = requests.get(story_url)
                        ext = story_url.split('.')[-1].split('?')[0]
                        fname = f"story.{ext}"
                        with open(fname, "wb") as f:
                            f.write(response.content)
                        if ext in ["jpg", "jpeg", "png"]:
                            with open(fname, "rb") as img_file:
                                await update.message.reply_photo(photo=img_file)
                        else:
                            with open(fname, "rb") as vid_file:
                                await update.message.reply_video(video=vid_file)
                        os.remove(fname)
                    except Exception as e:
                        await update.message.reply_text(f"❌ خطا در ارسال استوری: {e}")
            else:
                await update.message.reply_text(f"❌ خطا: {error}")
        else:
            await update.message.reply_text("⚠️ لطفاً لینک پست یا آیدی پیج اینستاگرام را ارسال کنید!")
    elif mode == "youtube":
        if "youtube.com" not in message_text and "youtu.be" not in message_text:
            await update.message.reply_text("⚠️ لطفاً فقط لینک یوتیوب ارسال کنید!")
            return
        await update.message.reply_text("⏳ در حال دانلود ویدیو یوتیوب...")
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                file_path, title = download_youtube_video(message_text, temp_dir)
                file_size = os.path.getsize(file_path)
                if file_size >= MAX_FILESIZE:
                    await update.message.reply_text('❌ حجم فایل نهایی بیشتر از 50MB است و قابل ارسال نیست.')
                    return
                with open(file_path, "rb") as f:
                    await update.message.reply_video(video=f, caption=title)
                update_stats("youtube")  # ثبت آمار
            except Exception as e:
                log_error(f"خطا در دانلود یوتیوب: {e}", user.id)
                logger.error(f"Error: {str(e)}", exc_info=True)
                await update.message.reply_text(f"❌ خطا در دانلود یا ارسال ویدیو: {e}")
    elif mode == "insta_profile":
        insta_id = message_text.strip()
        if not re.match(r'^[A-Za-z0-9_.]+$', insta_id):
            await update.message.reply_text("⚠️ لطفاً فقط آیدی معتبر اینستاگرام ارسال کنید!")
            return
        await update.message.reply_text("⏳ در حال دریافت اطلاعات پیج اینستاگرام...")
        try:
            info, profile_pic_url, error = get_instagram_profile_info(insta_id)
            if info:
                if profile_pic_url:
                    await update.message.reply_photo(photo=profile_pic_url)
                await update.message.reply_text(info)
                update_stats("insta_profile")  # ثبت آمار
            else:
                log_error(f"خطا در دریافت اطلاعات پیج اینستاگرام: {error}", user.id)
                await update.message.reply_text(f"❌ خطا: {error}")
        except Exception as e:
            log_error(f"خطا کلی در دریافت اطلاعات پیج اینستاگرام: {e}", user.id)
            await update.message.reply_text(f"❌ خطا در پردازش: {e}")
    elif mode == "youtube_channel":
        channel_id_or_url = message_text.strip()
        await update.message.reply_text("⏳ در حال دریافت اطلاعات کانال یوتیوب...")
        try:
            info, profile_pic_url, error = get_youtube_channel_info(channel_id_or_url)
            if info:
                if profile_pic_url:
                    await update.message.reply_photo(photo=profile_pic_url)
                await update.message.reply_text(info)
                update_stats("youtube_channel")  # ثبت آمار
            else:
                log_error(f"خطا در دریافت اطلاعات کانال یوتیوب: {error}", user.id)
                await update.message.reply_text(f"❌ خطا: {error}")
        except Exception as e:
            log_error(f"خطا کلی در دریافت اطلاعات کانال یوتیوب: {e}", user.id)
            await update.message.reply_text(f"❌ خطا در پردازش: {e}")
    else:
        await update.message.reply_text("👇 ابتدا یکی از گزینه‌های منو را انتخاب کنید.")

def get_instagram_profile_info(username):
    try:
        L = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(L.context, username)
        info = (
            f"🔍 اطلاعات پیج @{username}:\n"
            f"👤 نام کامل: {profile.full_name}\n"
            f"🆔 آیدی: {profile.username}\n"
            f"📷 تعداد پست‌ها: {profile.mediacount}\n"
            f"👥 تعداد فالوور: {profile.followers}\n"
            f"👤 تعداد فالووینگ: {profile.followees}\n"
            f"🔒 خصوصی: {'بله' if profile.is_private else 'خیر'}\n"
            f"✅ تایید شده: {'بله' if profile.is_verified else 'خیر'}\n"
            f"🌐 بیو: {profile.biography}"
        )
        profile_pic_url = profile.profile_pic_url
        return info, profile_pic_url, None
    except Exception as e:
        return None, None, str(e)

def get_youtube_channel_info(channel_id_or_url):
    try:
        if not channel_id_or_url.startswith("http"):
            url = f"https://www.youtube.com/channel/{channel_id_or_url}"
        else:
            url = channel_id_or_url
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'skip_download': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        subscriber_count = info.get('subscriber_count', '---')
        channel_id = info.get('id', None)
        if YOUTUBE_API_KEY and channel_id:
            api_subs = get_youtube_subscribers_api(channel_id)
            if api_subs:
                subscriber_count = api_subs
        channel_info = (
            f"🔍 اطلاعات کانال یوتیوب:\n"
            f"📛 نام کانال: {info.get('title', '---')}\n"
            f"🆔 آیدی/URL: {info.get('id', '---')}\n"
            f"👥 تعداد سابسکرایبر: {subscriber_count}\n"
            f"🎬 تعداد ویدیو: {info.get('playlist_count', '---')}\n"
            f"📝 توضیحات: {info.get('description', '---')}\n"
            f"🌐 لینک: {info.get('webpage_url', url)}"
        )
        profile_pic_url = None
        if 'thumbnails' in info and info['thumbnails']:
            profile_pic_url = info['thumbnails'][-1]['url']
        elif 'thumbnail' in info:
            profile_pic_url = info['thumbnail']
        return channel_info, profile_pic_url, None
    except Exception as e:
        return None, None, str(e)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ADMIN", admin_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
