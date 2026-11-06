import sqlite3
import time
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ============================================================
# ⚙️ تنظیمات
# ============================================================
TOKEN = "9059341109:AAFzNGbEsKV21PaLP3ba-P8WtBFUj-CZMUY" # <--- توکن ربات
ADMIN_ID = 7458169181 # <--- آیدی عددی تلگرام خودت رو اینجا بذار (بدون @)
DB = "life.db"

WORK_COOLDOWN = 60 * 60
DAILY_COOLDOWN = 60 * 60 * 24
ENERGY_REGEN_SEC = 300
AGE_UP_SEC = 60 * 60 * 24 * 3
JAIL_TIME = 60 * 15 # ۱۵ دقیقه زندان
HOME_COOLDOWN = 60 * 60 * 2 # ۲ ساعت محدودیت خونه
FIGHT_COOLDOWN = 60 * 60 # ۱ ساعت محدودیت دعوا
HANG_OUT_COOLDOWN = 60 * 60 # ۱ ساعت محدودیت بیرون رفتن با دوست

JOBS = {
    "برنامه‌نویس": {"salary": 400, "min_age": 18, "min_edu": 2},
    "هکر":        {"salary": 700, "min_age": 20, "min_edu": 2},
    "معلم":       {"salary": 300, "min_age": 20, "min_edu": 2},
    "دکتر":       {"salary": 800, "min_age": 24, "min_edu": 3},
    "مهندس":      {"salary": 500, "min_age": 22, "min_edu": 3},
    "بازیگر":     {"salary": 600, "min_age": 18, "min_edu": 1},
    "ورزشکار":    {"salary": 450, "min_age": 18, "min_edu": 1},
    "تاجر":       {"salary": 900, "min_age": 25, "min_edu": 2},
    "مدیرعامل":   {"salary": 2000, "min_age": 30, "min_edu": 3},
    "راننده":     {"salary": 200, "min_age": 18, "min_edu": 0},
    "آشپز":       {"salary": 250, "min_age": 18, "min_edu": 1},
    "بیکار":      {"salary": 0,   "min_age": 0,  "min_edu": 0},
}

EDU_LEVELS = ["بی‌سواد", "دبستان", "دبیرستان", "دانشگاه"]
EDU_COST = [0, 1000, 3000, 8000]
EDU_TIME = [0, 60*30, 60*60*6, 60*60*24]

HOUSES = {
    "اجاره‌ای": {"price": 0, "happy": 0}, 
    "آپارتمان": {"price": 15000, "happy": 15}, 
    "ویلا": {"price": 50000, "happy": 35}, 
    "عمارت": {"price": 150000, "happy": 60},
    "پنت‌هاوس": {"price": 500000, "happy": 100}
}
CARS = {
    "دوچرخه": {"price": 2000, "happy": 5}, 
    "پراید": {"price": 10000, "happy": 10}, 
    "بنز": {"price": 80000, "happy": 30},
    "مکلارن": {"price": 300000, "happy": 70}
}
FOODS = {
    "نان": {"price": 50, "energy": 10, "health": 2}, 
    "پیتزا": {"price": 150, "energy": 30, "health": 5}, 
    "غذای رستوران": {"price": 500, "energy": 50, "health": 15},
    "کباب لوکس": {"price": 1500, "energy": 100, "health": 30}
}
FUN = {
    "پارک": {"price": 0, "happy": 10, "energy": -5}, 
    "سینما": {"price": 200, "happy": 20, "energy": -10}, 
    "کنسرت": {"price": 800, "happy": 40, "energy": -20}, 
    "مسافرت": {"price": 3000, "happy": 80, "energy": -30}
}

# ============================================================
# 🗄 دیتابیس
# ============================================================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY, name TEXT, gender TEXT, age INTEGER DEFAULT 18,
        money INTEGER DEFAULT 5000, bank INTEGER DEFAULT 0, debt INTEGER DEFAULT 0,
        energy INTEGER DEFAULT 100, health INTEGER DEFAULT 100, happiness INTEGER DEFAULT 50,
        education INTEGER DEFAULT 0, edu_finish INTEGER DEFAULT 0, job TEXT DEFAULT 'بیکار',
        house TEXT DEFAULT 'اجاره‌ای', car TEXT DEFAULT NULL, car_broken INTEGER DEFAULT 0, 
        children INTEGER DEFAULT 0, 
        level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, jail_until INTEGER DEFAULT 0,
        last_work INTEGER DEFAULT 0, last_daily INTEGER DEFAULT 0, last_energy INTEGER DEFAULT 0,
        last_age INTEGER DEFAULT 0, last_home INTEGER DEFAULT 0, last_fight INTEGER DEFAULT 0,
        last_hangout INTEGER DEFAULT 0, alive INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS friends (user_id1 INTEGER, user_id2 INTEGER, PRIMARY KEY (user_id1, user_id2))""")
    c.execute("""CREATE TABLE IF NOT EXISTS trials (msg_id INTEGER PRIMARY KEY, user_id INTEGER, votes_free INTEGER, votes_jail INTEGER, end_time INTEGER)""")
    conn.commit()
    conn.close()

PLAYER_KEYS = ["user_id","name","gender","age","money","bank","debt","energy","health","happiness",
               "education","edu_finish","job","house","car","car_broken","children",
               "level","xp","jail_until","last_work","last_daily","last_energy","last_age","last_home","last_fight","last_hangout","alive"]

def get_player(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(zip(PLAYER_KEYS, row)) if row else None

def create_player(user_id, name, gender):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = int(time.time())
    c.execute("INSERT OR IGNORE INTO players (user_id, name, gender, last_energy, last_age, last_home, last_fight, last_hangout) VALUES (?,?,?,?,?,?,?,?)", (user_id, name, gender, now, now, 0, 0, 0))
    conn.commit()
    conn.close()

def update_player(user_id, **kwargs):
    if not kwargs: return
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    c.execute(f"UPDATE players SET {fields} WHERE user_id=?", values)
    conn.commit()
    conn.close()

def delete_player(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM players WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM friends WHERE user_id1=? OR user_id2=?", (user_id, user_id))
    conn.commit()
    conn.close()

def add_friend(u1, u2):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO friends (user_id1, user_id2) VALUES (?,?)", (u1, u2))
    c.execute("INSERT OR IGNORE INTO friends (user_id1, user_id2) VALUES (?,?)", (u2, u1))
    conn.commit()
    conn.close()

def get_friends(u):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT user_id2 FROM friends WHERE user_id1=?", (u,))
    r = [x[0] for x in c.fetchall()]
    conn.close()
    return r

def regen_energy(p):
    now = int(time.time())
    gain = (now - p["last_energy"]) // ENERGY_REGEN_SEC
    if gain > 0: return min(100, p["energy"] + gain), now
    return p["energy"], p["last_energy"]

def add_xp(uid, p, amount):
    xp = p["xp"] + amount
    level = p["level"]
    while xp >= level * 100:
        xp -= level * 100
        level += 1
    update_player(uid, xp=xp, level=level)
    return level - p["level"]

def clamp(v, lo=0, hi=100): return max(lo, min(hi, v))

def is_in_jail(p): return p["jail_until"] > int(time.time())

# ============================================================
# 🤖 دستورات ربات
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = get_player(uid)
    if p:
        await update.message.reply_text(f"👋 سلام {p['name']} عزیز!\nدلم برات تنگ شده بود. 😊\nبرای دیدن وضعیتت بزن: **وضعیت**")
        return
    kb = [[InlineKeyboardButton("👨 مرد", callback_data="gender_male")], [InlineKeyboardButton("👩 زن", callback_data="gender_female")]]
    await update.message.reply_text("🎮 **به شبیه‌ساز زندگی خوش اومدی!**\n\nاینجا یه زندگی جدید داری، می‌تونی کار کنی، خونه بخری یا حتی بری زندان! 😎\n\nبرای شروع، **جنسیتت** رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

async def gender_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["gender"] = "male" if q.data == "gender_male" else "female"
    context.user_data["awaiting_name"] = True
    await q.edit_message_text("📝 حالا یه **اسم** خوشگل برای شخصیتت بفرست (بین ۲ تا ۲۰ حرف):")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_name"):
        name = update.message.text.strip()[:20]
        if len(name) < 2:
            await update.message.reply_text("⚠️ اسم باید حداقل ۲ حرف باشه! دوباره بفرست:")
            return
        uid = update.effective_user.id
        create_player(uid, name, context.user_data["gender"])
        context.user_data["awaiting_name"] = False
        await update.message.reply_text(
            f"🎉 **تبریک! شخصیت «{name}» با موفقیت ساخته شد.**\n"
            f"💰 **بودجه اولیه:** 5,000 تومان\n"
            f"━━━━━━━━━━━━━━━\n"
            "💡 **دیگه نیازی به اسلش (/) نداری!**\n"
            "کافیه این کلمات رو تایپ کنی:\n\n"
            "📊 وضعیت | 💼 کار | 💰 حقوق | 🎓 شغل | 📚 درس\n"
            "🏦 بانک | 💳 وام | 🛒 خرید | 🍔 غذا | 🎉 تفریح\n"
            "🏥 بیمارستان | 🥊 دعوا (با ریپلای) | 🛠 تعمیرگاه\n"
            "🤝 دوست (با ریپلای) | 👥 دوستام | 🏠 خونه\n"
            "🚗 رفتن بیرون (با ریپلای) | 🏆 لیدر | ⛓ زندان | ⚖️ درخواست آزادی"
        )
        return

    text = update.message.text.strip()
    p = get_player(update.effective_user.id)
    if not p: return

    # پنل مدیریت
    if text == "پنل" and update.effective_user.id == ADMIN_ID:
        await admin_panel(update, context)
        return

    if text in ["وضعیت", "من", "حساب من"]: await me(update, context)
    elif text in ["کار", "برو سر کار"]: await work(update, context)
    elif text in ["حقوق", "پول تو جیبی"]: await daily(update, context)
    elif text in ["شغل", "کار پیدا کن"]: await job(update, context)
    elif text in ["تحصیل", "درس", "درس بخون", "مدرسه"]: await edu(update, context)
    elif text in ["بانک", "پول بذار بانک"]: await bank(update, context)
    elif text in ["وام", "قرض"]: await loan(update, context)
    elif text in ["خرید", "مغازه", "فروشگاه"]: await shop(update, context)
    elif text in ["غذا", "گشنمه", "رستوران"]: await food(update, context)
    elif text in ["تفریح", "بیرون بریم"]: await fun(update, context)
    elif text in ["بیمارستان", "دکتر"]: await hospital(update, context)
    elif text in ["تیمارستان"]: await asylum(update, context)
    elif text in ["دعوا", "بزنش"]: await fight(update, context)
    elif text in ["تعمیرگاه", "ماشینم خرابه"]: await garage(update, context)
    elif text in ["دوست", "دوست بشیم"]: await make_friend(update, context)
    elif text in ["دوستام", "دوستان"]: await my_friends(update, context)
    elif text in ["خونه", "برو خونه"]: await go_myhome(update, context)
    elif text in ["بریم خونه‌ش", "خونه دوستم", "رفتن بیرون"]: await visit_home(update, context)
    elif text in ["سوپرمارکت"]: await supermarket(update, context)
    elif text.startswith("پول "):
        try:
            amount = text.split(" ")[1]
            context.args = [amount]
            await give(update, context)
        except IndexError: await update.message.reply_text("⚠️ مبلغ رو درست بگو (مثلاً: پول ۱۰۰)")
    elif text in ["لیدر", "ثروتمندترین"]: await top(update, context)
    elif text in ["زندان", "وضعیت زندان"]: await jail_status(update, context)
    elif text in ["درخواست آزادی", "دادگاه"]: await request_trial(update, context)

# ------------------ پنل ادمین ------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("💰 افزایش پول همه", callback_data="admin_money_all")],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast")]
    ]
    await update.message.reply_text("👑 **پنل مدیریت (مالک)**\n\nیکی از گزینه‌ها رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "admin_money_all":
        conn = sqlite3.connect(DB); c = conn.cursor()
        c.execute("UPDATE players SET money = money + 10000")
        conn.commit(); conn.close()
        await q.edit_message_text("✅ **10,000 تومان به حساب همه کاربران اضافه شد!**")
    elif q.data == "admin_broadcast":
        await q.edit_message_text("⚠️ قابلیت پیام همگانی در آپدیت‌های بعدی اضافه میشه.")

# ------------------ اکشن‌های بازی ------------------
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول با /start یه شخصیت بساز!")
    
    e, last = regen_energy(p)
    if e != p["energy"]:
        update_player(uid, energy=e, last_energy=last)
        p["energy"] = e
        
    gender = "👨" if p["gender"] == "male" else "👩"
    car_status = f"🚗 {p['car']}" if p['car'] else "❌ ندارد"
    if p['car'] and p['car_broken']: car_status += " (خراب 🛠)"
        
    username = f" (@{update.effective_user.username})" if update.effective_user.username else ""
    jail_status = ""
    if is_in_jail(p):
        left = (p["jail_until"] - int(time.time())) // 60
        jail_status = f"\n⛓ **تو زندانی هستی!** ({left} دقیقه مونده)"
        
    await update.message.reply_text(
        f"👤 **{p['name']}**{username} — 🌟 سطح {p['level']} ({p['xp']} XP)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{gender} جنسیت: {'مرد' if p['gender'] == 'male' else 'زن'}\n"
        f"🎂 سن: {p['age']}\n"
        f"🎓 تحصیلات: {EDU_LEVELS[p['education']]}\n"
        f"💼 شغل: {p['job']}\n"
        f"🏠 خونه: {p['house']}\n"
        f"{car_status}\n"
        f"💰 پول: {p['money']} | 🏦 بانک: {p['bank']} | 💳 بدهی: {p['debt']}\n"
        f"⚡ انرژی: {p['energy']}/100\n"
        f"❤️ سلامت: {p['health']}/100\n"
        f"😊 شادی: {p['happiness']}/100\n"
        f"👶 بچه‌ها: {p['children']}"
        f"{jail_status}"
    )

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی، دسترسی نداری! (درخواست آزادی بده)")
    if p["job"] == "بیکار": return await update.message.reply_text("🤷‍♂️ اول باید یه شغل انتخاب کنی! (کلمه: شغل)")
    if p["energy"] < 10: return await update.message.reply_text("😴 انرژی نداری! یه چیزی بخور (کلمه: غذا) یا یه کم صبر کن.")
    if p["health"] < 10: return await update.message.reply_text("🤒 حالت خوب نیست! اول برو بیمارستان.")
    
    now = int(time.time())
    if now - p["last_work"] < WORK_COOLDOWN:
        left = WORK_COOLDOWN - (now - p["last_work"])
        return await update.message.reply_text(f"⏳ هنوز خسته‌ای! {left//60} دقیقه دیگه می‌تونی کار کنی.")
        
    salary = JOBS[p["job"]]["salary"]
    if random.random() < 0.1:
        salary *= 2
        await update.message.reply_text("🎁 **ایول! پاداش گرفتی، حقوقت دو برابر شد!**")
    if random.random() < 0.05:
        await update.message.reply_text("😷 **اوه! خیلی خسته شدی و مریض شدی.**")
        update_player(uid, health=clamp(p["health"]-10))
        
    update_player(uid, money=p["money"]+salary, energy=clamp(p["energy"]-10), last_work=now)
    lvl = add_xp(uid, p, 5)
    
    msg = f"💼 **کارت تموم شد!**\n💰 حقوق: +{salary} تومان\n💵 پول فعلی: {p['money']+salary}"
    if lvl: msg += f"\n🌟 **سطحت رفت بالا!** حالا سطح {p['level']+lvl} هستی."
    await update.message.reply_text(msg)

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    now = int(time.time())
    if now - p["last_daily"] < DAILY_COOLDOWN:
        left = DAILY_COOLDOWN - (now - p["last_daily"])
        return await update.message.reply_text(f"⏳ امروز حقوق گرفتی! {left//3600} ساعت دیگه بیا.")
    reward = 500 + p["age"]*10 + p["level"]*100
    update_player(uid, money=p["money"]+reward, last_daily=now)
    await update.message.reply_text(f"🎁 **حقوق روزانه!**\n💵 +{reward} تومان به پولت اضافه شد.")

async def job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    kb = []
    for name, info in JOBS.items():
        if name == "بیکار": continue
        if p["age"] >= info["min_age"] and p["education"] >= info["min_edu"]:
            kb.append([InlineKeyboardButton(f"{name} (حقوق: {info['salary']})", callback_data=f"job_{name}")])
    if not kb: return await update.message.reply_text("🎓 هنوز شرایط شغلی نداری! اول باید درس بخونی (کلمه: درس).")
    await update.message.reply_text("💼 **لیست شغل‌های موجود:**\nیکی رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

async def job_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    update_player(q.from_user.id, job=q.data.replace("job_", ""))
    await q.edit_message_text(f"✅ **تبریک! شغل تو شد: {q.data.replace('job_', '')}**\nحالا می‌تونی کار کنی (کلمه: کار)")

async def edu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    nxt = p["education"] + 1
    if nxt >= len(EDU_LEVELS): return await update.message.reply_text("🎓 **ایول! تو دیگه بالاترین مدرک تحصیلی رو داری.**")
    kb = [[InlineKeyboardButton(f"ثبت‌نام ({EDU_COST[nxt]} تومان)", callback_data=f"edu_{nxt}")]]
    await update.message.reply_text(f"🎓 **ارتقا به {EDU_LEVELS[nxt]}**\n💰 هزینه: {EDU_COST[nxt]} تومان\n⏳ زمان: {EDU_TIME[nxt]//60} دقیقه", reply_markup=InlineKeyboardMarkup(kb))

async def edu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    nxt = int(q.data.replace("edu_", ""))
    uid = q.from_user.id; p = get_player(uid)
    if p["money"] < EDU_COST[nxt]: return await q.edit_message_text("❌ **پول کافی نداری!** برو کار کن.")
    update_player(uid, money=p["money"]-EDU_COST[nxt], edu_finish=int(time.time())+EDU_TIME[nxt])
    await q.edit_message_text(f"📚 **تحصیل شروع شد!**\nبعد از {EDU_TIME[nxt]//60} دقیقه با /finish_edu تمومش کن.")

async def finish_edu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p or not p["edu_finish"]: return await update.message.reply_text("⚠️ تحصیلی در جریان نیست.")
    if int(time.time()) < p["edu_finish"]:
        left = p["edu_finish"] - int(time.time())
        return await update.message.reply_text(f"⏳ هنوز {left//60} دقیقه مونده! صبر کن.")
    update_player(uid, education=p["education"]+1, edu_finish=0)
    await update.message.reply_text(f"🎓 **تبریک! مدرک {EDU_LEVELS[p['education']+1]} گرفتی.**")

async def bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    kb = [[InlineKeyboardButton("💰 واریز همه پول", callback_data="bank_deposit")], [InlineKeyboardButton("🏦 برداشت همه", callback_data="bank_withdraw")]]
    await update.message.reply_text(f"🏦 **بانک مرکزی**\n💰 پول نقد: {p['money']}\n🏦 موجودی بانک: {p['bank']}\n💳 بدهی: {p['debt']}\n\n(بانک هر ساعت ۱٪ سود میده)", reply_markup=InlineKeyboardMarkup(kb))

async def bank_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; p = get_player(uid)
    if q.data == "bank_deposit":
        update_player(uid, bank=p["bank"]+p["money"], money=0)
        await q.edit_message_text(f"✅ **{p['money']} تومان با موفقیت واریز شد.**")
    else:
        update_player(uid, money=p["money"]+p["bank"], bank=0)
        await q.edit_message_text(f"✅ **{p['bank']} تومان برداشت شد.**")

async def loan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    kb = [[InlineKeyboardButton("گرفتن وام 10,000", callback_data="loan_10000")]]
    await update.message.reply_text("💳 **وام بانکی**\nمبلغ وام: 10,000 تومان\nبدهی که باید پس بدی: 12,000 تومان\n\nقبول می‌کنی؟", reply_markup=InlineKeyboardMarkup(kb))

async def loan_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    amount = int(q.data.replace("loan_", ""))
    uid = q.from_user.id; p = get_player(uid)
    update_player(uid, money=p["money"]+amount, debt=p["debt"]+int(amount*1.2))
    await q.edit_message_text(f"💳 **وام گرفتی!**\n💰 +{amount} تومان به پولت اضافه شد.\n💳 بدهی کل: {p['debt']+int(amount*1.2)}")

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    kb = []
    for h, info in HOUSES.items():
        if h != "اجاره‌ای" and h != p["house"]: kb.append([InlineKeyboardButton(f"🏠 {h} — {info['price']}", callback_data=f"house_{h}")])
    for c, info in CARS.items():
        if c != p["car"]: kb.append([InlineKeyboardButton(f"🚗 {c} — {info['price']}", callback_data=f"car_{c}")])
    await update.message.reply_text("🛒 **فروشگاه بزرگ**\nچی می‌خوای بخری؟", reply_markup=InlineKeyboardMarkup(kb))

async def shop_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; p = get_player(uid)
    if q.data.startswith("house_"):
        h = q.data.replace("house_", "")
        if p["money"] < HOUSES[h]["price"]: return await q.edit_message_text("❌ **پول کافی نداری!**")
        update_player(uid, money=p["money"]-HOUSES[h]["price"], house=h, happiness=clamp(p["happiness"]+HOUSES[h]["happy"]))
        await q.edit_message_text(f"🏠 **تبریک! {h} خریدی.**")
    elif q.data.startswith("car_"):
        c = q.data.replace("car_", "")
        if p["money"] < CARS[c]["price"]: return await q.edit_message_text("❌ **پول کافی نداری!**")
        update_player(uid, money=p["money"]-CARS[c]["price"], car=c, car_broken=0, happiness=clamp(p["happiness"]+CARS[c]["happy"]))
        await q.edit_message_text(f"🚗 **ایول! {c} خریدی.**")

async def food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    kb = [[InlineKeyboardButton(f"{f} — {info['price']}", callback_data=f"food_{f}")] for f, info in FOODS.items()]
    await update.message.reply_text("🍔 **چی می‌خوری؟**", reply_markup=InlineKeyboardMarkup(kb))

async def food_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    f = q.data.replace("food_", "")
    uid = q.from_user.id; p = get_player(uid)
    if p["money"] < FOODS[f]["price"]: return await q.edit_message_text("❌ **پول کمه!**")
    update_player(uid, money=p["money"]-FOODS[f]["price"], energy=clamp(p["energy"]+FOODS[f]["energy"]), health=clamp(p["health"]+FOODS[f]["health"]))
    await q.edit_message_text(f"🍽 **نوش جان! {f} خوردی.**\n⚡ انرژی: {clamp(p['energy']+FOODS[f]['energy'])}")

async def fun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    kb = [[InlineKeyboardButton(f"{f} — {info['price']}", callback_data=f"fun_{f}")] for f, info in FUN.items()]
    await update.message.reply_text("🎉 **کجا بریم؟**", reply_markup=InlineKeyboardMarkup(kb))

async def fun_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    f = q.data.replace("fun_", "")
    uid = q.from_user.id; p = get_player(uid)
    if p["money"] < FUN[f]["price"]: return await q.edit_message_text("❌ **پول کمه!**")
    update_player(uid, money=p["money"]-FUN[f]["price"], happiness=clamp(p["happiness"]+FUN[f]["happy"]), energy=clamp(p["energy"]+FUN[f]["energy"]))
    await q.edit_message_text(f"🎉 **چه کیفیتی! به {f} رفتی.**\n😊 شادی: {clamp(p['happiness']+FUN[f]['happy'])}")

async def hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی، دسترسی نداری.")
    if p["health"] >= 100: return await update.message.reply_text("❤️ **سلامتیت کامله!** نیازی به دکتر نداری.")
    cost = (100 - p["health"]) * 20
    kb = [[InlineKeyboardButton(f"بستری شدن ({cost} تومان)", callback_data=f"hosp_{cost}")]]
    await update.message.reply_text(f"🏥 **بیمارستان**\n❤️ سلامت فعلی: {p['health']}/100\n💉 هزینه درمان: {cost} تومان", reply_markup=InlineKeyboardMarkup(kb))

async def hospital_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cost = int(q.data.replace("hosp_", ""))
    uid = q.from_user.id; p = get_player(uid)
    if p["money"] < cost: return await q.edit_message_text("❌ **پول کافی برای درمان نداری!**")
    update_player(uid, money=p["money"]-cost, health=100)
    await q.edit_message_text("💉 **درمان انجام شد!** سلامتیت به 100 برگشت. ❤️")

async def asylum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی!")
    if p["happiness"] >= 30 and p["health"] >= 30: 
        return await update.message.reply_text("😊 **تو که حالت خوبه!** تیمارستان مال وقتیه که شادی یا سلامتت خیلی کم شده باشه.")
    await update.message.reply_text(f"🏥 **{p['name']} رو به تیمارستان بردن!**\nچند روز تحت نظر بود و حالا حالش بهتره. 🩺")
    update_player(uid, happiness=clamp(p["happiness"]+50), health=clamp(p["health"]+30))

async def fight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی!")
    
    # محدودیت ساعت دعوا (۸ صبح تا ۱۲ شب)
    current_hour = int(time.strftime("%H", time.localtime()))
    if current_hour < 8 or current_hour >= 24:
        return await update.message.reply_text("🕒 **دعوا فقط بین ساعت ۸ صبح تا ۱۲ شب امکان‌پذیره!** برو بخواب 😴")

    # محدودیت یک بار در ساعت
    now = int(time.time())
    if now - p["last_fight"] < FIGHT_COOLDOWN:
        left = FIGHT_COOLDOWN - (now - p["last_fight"])
        return await update.message.reply_text(f"⏳ **تازه دعوا کردی!** {left//60} دقیقه دیگه می‌تونی دوباره دعوا کنی.")

    if not update.message.reply_to_message: return await update.message.reply_text("🥊 برای دعوا، روی پیام طرف ریپلای کن و بنویس: **دعوا**")
    t_id = update.message.reply_to_message.from_user.id
    if t_id == uid: return await update.message.reply_text("😅 **با خودت دعوا نکن!**")
    t = get_player(t_id)
    if not t: return await update.message.reply_text("طرف شخصیت نداره.")
    if is_in_jail(t): return await update.message.reply_text("⛓ طرف زندانیه، نمی‌تونی بزنیش!")
    if p["energy"] < 20: return await update.message.reply_text("⚡ **انرژی برای دعوا نداری!**")
    
    update_player(uid, last_fight=now) # ثبت زمان دعوا
    
    if random.random() < 0.3:
        jail_time = int(time.time()) + JAIL_TIME
        update_player(uid, money=max(0, p["money"]-1000), energy=clamp(p["energy"]-15), jail_until=jail_time)
        update_player(t_id, money=max(0, t["money"]-1000), energy=clamp(t["energy"]-15))
        await update.message.reply_text(f"🚨 **پلیس سر رسید!**\n👮‍♂️ {p['name']} رو دستگیر کرد و برد زندان (۱۵ دقیقه)!\n💸 هردوتون 1,000 تومان جریمه شدید.")
        return

    power_p = (p["energy"] * 0.5) + (p["happiness"] * 0.3) + random.randint(1, 50)
    power_t = (t["energy"] * 0.5) + (t["happiness"] * 0.3) + random.randint(1, 50)
    
    if power_p > power_t:
        stolen = min(t["money"], 500)
        update_player(uid, energy=clamp(p["energy"]-20), health=clamp(p["health"]-10), money=p["money"]+stolen)
        update_player(t_id, health=clamp(t["health"]-20), money=t["money"]-stolen)
        await update.message.reply_text(f"🥊 **{p['name']} تونست {t['name']} رو بزنه!**\n💰 {stolen} تومان ازش گرفت.")
    else:
        stolen = min(p["money"], 500)
        update_player(uid, energy=clamp(p["energy"]-20), health=clamp(p["health"]-20), money=p["money"]-stolen)
        update_player(t_id, health=clamp(t["health"]-10), money=t["money"]+stolen)
        await update.message.reply_text(f"🥊 **{t['name']} تونست {p['name']} رو بزنه!**\n💰 {stolen} تومان ازش گرفت.")

async def jail_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if not is_in_jail(p): return await update.message.reply_text("🕊 **تو زندانی نیستی!** آزادی.")
    left = (p["jail_until"] - int(time.time())) // 60
    await update.message.reply_text(f"⛓ **تو زندانی هستی!**\n⏳ {left} دقیقه تا آزادی مونده.\n⚖️ برای درخواست دادگاه بنویس: درخواست آزادی")

async def request_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if not is_in_jail(p): return await update.message.reply_text("⚠️ تو زندانی نیستی که دادگاه بخوای!")
    
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT 1 FROM trials WHERE user_id=? AND end_time > ?", (uid, int(time.time())))
    if c.fetchone():
        conn.close()
        return await update.message.reply_text("⏳ **یه دادگاه برای تو در حال برگزاریه،** صبر کن تموم بشه.")
    conn.close()

    kb = [
        [InlineKeyboardButton("✅ آزاد بشه", callback_data=f"vote_free_{uid}")],
        [InlineKeyboardButton("❌ بمونه زندان", callback_data=f"vote_jail_{uid}")]
    ]
    
    msg = await update.message.reply_text(
        f"⚖️ **دادگاه برای {p['name']}**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"ایشان درخواست آزادی داده. ای مردم! رای بدید:\n"
        f"⏳ زمان رای‌گیری: ۱ دقیقه",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("INSERT INTO trials (msg_id, user_id, votes_free, votes_jail, end_time) VALUES (?,?,?,?,?)", (msg.message_id, uid, 0, 0, int(time.time()) + 60))
    conn.commit()
    conn.close()

    asyncio.create_task(end_trial_delayed(msg.message_id, msg.chat_id, 60))

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    action, target_uid = q.data.split("_")[1], int(q.data.split("_")[2])
    voter_id = q.from_user.id
    
    if voter_id == target_uid:
        return await q.answer("😅 نمی‌تونی به نفع خودت رای بدی!", show_alert=True)

    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT votes_free, votes_jail, end_time FROM trials WHERE msg_id=?", (q.message.message_id,))
    row = c.fetchone()
    
    if not row or int(time.time()) > row[2]:
        conn.close()
        return await q.answer("⏳ این دادگاه تموم شده!", show_alert=True)
    
    if action == "free":
        c.execute("UPDATE trials SET votes_free=votes_free+1 WHERE msg_id=?", (q.message.message_id,))
        await q.answer("✅ رای به آزادی ثبت شد.")
    else:
        c.execute("UPDATE trials SET votes_jail=votes_jail+1 WHERE msg_id=?", (q.message.message_id,))
        await q.answer("❌ رای به زندان ثبت شد.")
        
    conn.commit()
    conn.close()

async def end_trial_delayed(msg_id, chat_id, delay):
    await asyncio.sleep(delay)
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT user_id, votes_free, votes_jail FROM trials WHERE msg_id=?", (msg_id,))
    row = c.fetchone()
    c.execute("DELETE FROM trials WHERE msg_id=?", (msg_id,))
    conn.commit(); conn.close()
    
    if not row: return
    
    uid, v_free, v_jail = row
    p = get_player(uid)
    if not p: return
    
    text = f"⚖️ **حکم دادگاه برای {p['name']}**\n"
    text += f"━━━━━━━━━━━━━━━\n"
    text += f"✅ رای آزادی: {v_free}\n❌ رای زندان: {v_jail}\n\n"
    
    if v_free > v_jail:
        update_player(uid, jail_until=0)
        text += "🎉 **حکم: آزادی!**\nشما با رای مردم آزاد شدید."
    else:
        new_jail = int(time.time()) + JAIL_TIME * 2
        update_player(uid, jail_until=new_jail)
        text += f"⛓ **حکم: زندان!**\nشما باید {JAIL_TIME * 2 // 60} دقیقه دیگه هم بمونید."
        
    try:
        from telegram import Bot
        bot = Bot(token=TOKEN)
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        print("Error sending trial result:", e)

async def garage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی!")
    if not p["car"]: return await update.message.reply_text("🚗 **تو ماشینی نداری که خراب بشه!** برو یکی بخر (کلمه: خرید).")
    if not p["car_broken"]: return await update.message.reply_text("🚗 **ماشینت سالمه!** نیازی به تعمیر نداره.")
    cost = 3000
    kb = [[InlineKeyboardButton(f"تعمیر ({cost} تومان)", callback_data=f"repair_{cost}")]]
    await update.message.reply_text(f"🛠 **تعمیرگاه**\n🚗 ماشینت {p['car']} خراب شده.\n💸 هزینه تعمیر: {cost} تومان", reply_markup=InlineKeyboardMarkup(kb))

async def garage_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cost = int(q.data.replace("repair_", ""))
    uid = q.from_user.id; p = get_player(uid)
    if p["money"] < cost: return await q.edit_message_text("❌ **پول کافی نداری!**")
    update_player(uid, money=p["money"]-cost, car_broken=0)
    await q.edit_message_text("🛠 **ماشینت تعمیر شد!** حالا سالمه.")

async def make_friend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی!")
    if not update.message.reply_to_message: return await update.message.reply_text("🤝 برای دوست شدن، روی پیام طرف ریپلای کن و بنویس: **دوست**")
    t_id = update.message.reply_to_message.from_user.id
    if t_id == uid: return await update.message.reply_text("😅 **نمیشه با خودت دوست شد!**")
    t = get_player(t_id)
    if not t: return await update.message.reply_text("طرف شخصیت نداره.")
    add_friend(uid, t_id)
    await update.message.reply_text(f"🤝 **{p['name']} و {t['name']} با هم دوست شدن!**")

async def my_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    friends_list = get_friends(uid)
    if not friends_list: return await update.message.reply_text("👥 **تو هنوز دوستی نداری!** روی پیام بقیه ریپلای کن و بنویس: دوست")
    text = "👥 **لیست دوستان شما:**\n"
    text += "━━━━━━━━━━━━━━━\n"
    for f_id in friends_list:
        fp = get_player(f_id)
        if fp: text += f"• {fp['name']}\n"
    await update.message.reply_text(text)

async def go_myhome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی!")
    
    now = int(time.time())
    if now - p["last_home"] < HOME_COOLDOWN:
        left = HOME_COOLDOWN - (now - p["last_home"])
        return await update.message.reply_text(f"⏳ **برای استراحت باید {left//60} دقیقه دیگه صبر کنی.**")
        
    happy_gain = 15 if p["house"] == "اجاره‌ای" else 30
    update_player(uid, happiness=clamp(p["happiness"]+happy_gain), last_home=now)
    await update.message.reply_text(f"🏠 **{p['name']} رفت خونه‌ش ({p['house']}) و یه کم استراحت کرد.**\n😊 شادی +{happy_gain}")

async def visit_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی!")
    
    # محدودیت یک بار در ساعت برای بیرون رفتن
    now = int(time.time())
    if now - p["last_hangout"] < HANG_OUT_COOLDOWN:
        left = HANG_OUT_COOLDOWN - (now - p["last_hangout"])
        return await update.message.reply_text(f"⏳ **تازه با دوستت بیرون رفتی!** {left//60} دقیقه دیگه می‌تونی دوباره بری.")

    if not update.message.reply_to_message: return await update.message.reply_text("🏠 برای رفتن بیرون با دوستت، روی پیامش ریپلای کن و بنویس: **رفتن بیرون**")
    t_id = update.message.reply_to_message.from_user.id
    if t_id == uid: return await update.message.reply_text("😅 **برو خونه خودت!** (کلمه: خونه)")
    t = get_player(t_id)
    if not t: return await update.message.reply_text("طرف شخصیت نداره.")
    if t_id not in get_friends(uid): return await update.message.reply_text("❌ **شما با هم دوست نیستید!** اول با کلمه «دوست» دوست بشید.")
    
    update_player(uid, happiness=clamp(p["happiness"]+20), last_hangout=now)
    update_player(t_id, happiness=clamp(t["happiness"]+20))
    await update.message.reply_text(f"🏠 **{p['name']} رفت خونه {t['name']} و کلی باهم خوش گذروندن!**\n😊 شادی هر دو +20")

async def supermarket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی!")
    
    # محدودیت یک بار در ساعت برای بیرون رفتن
    now = int(time.time())
    if now - p["last_hangout"] < HANG_OUT_COOLDOWN:
        left = HANG_OUT_COOLDOWN - (now - p["last_hangout"])
        return await update.message.reply_text(f"⏳ **تازه با دوستت بیرون رفتی!** {left//60} دقیقه دیگه می‌تونی دوباره بری.")

    if not update.message.reply_to_message: return await update.message.reply_text("🛍 برای رفتن به سوپرمارکت، روی پیام دوستت ریپلای کن و بنویس: **سوپرمارکت**")
    t_id = update.message.reply_to_message.from_user.id
    if t_id == uid: return await update.message.reply_text("😅 **با خودت؟!**")
    t = get_player(t_id)
    if not t: return await update.message.reply_text("طرف شخصیت نداره.")
    if t_id not in get_friends(uid): return await update.message.reply_text("❌ **شما با هم دوست نیستید!** اول با کلمه «دوست» دوست بشید.")
    if p["money"] < 500 or t["money"] < 500: return await update.message.reply_text("❌ **هردوتون باید حداقل ۵۰۰ تومان داشته باشید.**")
    
    update_player(uid, money=p["money"]-500, energy=clamp(p["energy"]+30), health=clamp(p["health"]+15), happiness=clamp(p["happiness"]+10), last_hangout=now)
    update_player(t_id, money=t["money"]-500, energy=clamp(t["energy"]+30), health=clamp(t["health"]+15), happiness=clamp(t["happiness"]+10))
    await update.message.reply_text(f"🛒 **{p['name']} و {t['name']} با هم رفتن سوپرمارکت و کلی خرید کردن!**\n💸 هرکدوم ۵۰۰ تومان خرج کردن و انرژی و شادیشون بالا رفت. 🛍")

async def give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ اول /start بزن.")
    if is_in_jail(p): return await update.message.reply_text("⛓ تو زندانی هستی!")
    if not update.message.reply_to_message: return await update.message.reply_text("💸 برای انتقال پول، روی پیام طرف ریپلای کن و بنویس: **پول ۱۰۰**")
    try: amount = int(context.args[0])
    except: return await update.message.reply_text("⚠️ مبلغ رو درست بگو (مثلاً: پول 100)")
    if amount <= 0 or amount > p["money"]: return await update.message.reply_text("❌ **مبلغ نامعتبر!**")
    t_id = update.message.reply_to_message.from_user.id; t = get_player(t_id)
    if not t: return await update.message.reply_text("طرف شخصیت نداره.")
    update_player(uid, money=p["money"]-amount)
    update_player(t_id, money=t["money"]+amount)
    await update.message.reply_text(f"💸 **{amount} تومان به {t['name']} منتقل شد.**")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT name, money+bank, level FROM players ORDER BY money+bank DESC LIMIT 10")
    rows = c.fetchall(); conn.close()
    if not rows: return await update.message.reply_text("🏆 **هنوز بازیکنی نیست!**")
    text = "🏆 **ثروتمندترین‌های گروه:**\n"
    text += "━━━━━━━━━━━━━━━\n"
    for i, (n, m, l) in enumerate(rows, 1): text += f"{i}. {n} — {m} تومان (سطح {l})\n"
    await update.message.reply_text(text)

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; p = get_player(uid)
    if not p: return await update.message.reply_text("⚠️ شخصیتی نداری!")
    delete_player(uid)
    await update.message.reply_text("🗑 **شخصیتت حذف شد.**\nبرای شروع دوباره /start بزن.")

# ============================================================
# ⚡ تسک‌های پس‌زمینه
# ============================================================
async def regen_job():
    while True:
        try:
            conn = sqlite3.connect(DB); c = conn.cursor(); now = int(time.time())
            c.execute("SELECT user_id, energy, last_energy FROM players")
            for uid, e, last in c.fetchall():
                if e >= 100: c.execute("UPDATE players SET last_energy=? WHERE user_id=?", (now, uid)); continue
                g = (now - last) // ENERGY_REGEN_SEC
                if g > 0: c.execute("UPDATE players SET energy=?, last_energy=? WHERE user_id=?", (min(100, e+g), now, uid))
            conn.commit(); conn.close()
        except Exception as e: print("Regen Error:", e)
        await asyncio.sleep(ENERGY_REGEN_SEC)

async def age_job():
    while True:
        try:
            conn = sqlite3.connect(DB); c = conn.cursor(); now = int(time.time())
            c.execute("SELECT user_id, age, last_age, health FROM players")
            for uid, age, last, health in c.fetchall():
                if now - last >= AGE_UP_SEC:
                    new_age = age + 1
                    new_health = max(0, health - (1 if new_age > 60 else 0))
                    c.execute("UPDATE players SET age=?, last_age=?, health=? WHERE user_id=?", (new_age, now, new_health, uid))
                    if new_health <= 0: c.execute("UPDATE players SET alive=0 WHERE user_id=?", (uid,))
            conn.commit(); conn.close()
        except Exception as e: print("Age Error:", e)
        await asyncio.sleep(3600)

async def interest_job():
    while True:
        try:
            conn = sqlite3.connect(DB); c = conn.cursor()
            c.execute("SELECT user_id, bank FROM players")
            for uid, bank in c.fetchall():
                if bank > 0:
                    interest = int(bank * 0.01)
                    if interest > 0: c.execute("UPDATE players SET bank=bank+? WHERE user_id=?", (interest, uid))
            conn.commit(); conn.close()
        except Exception as e: print("Interest Error:", e)
        await asyncio.sleep(3600)

async def random_event_job():
    while True:
        try:
            conn = sqlite3.connect(DB); c = conn.cursor()
            c.execute("SELECT user_id, money, happiness, health, car, car_broken FROM players")
            for uid, money, happy, health, car, car_broken in c.fetchall():
                if random.random() < 0.1:
                    ev = random.choice(["bonus","sick","gift","accident","car_crash"])
                    if ev == "bonus": c.execute("UPDATE players SET money=money+500 WHERE user_id=?", (uid,))
                    elif ev == "sick": c.execute("UPDATE players SET health=? WHERE user_id=?", (max(0, health-15), uid))
                    elif ev == "gift": c.execute("UPDATE players SET money=money+300, happiness=? WHERE user_id=?", (min(100, happy+15), uid))
                    elif ev == "accident": c.execute("UPDATE players SET money=?, health=? WHERE user_id=?", (max(0, money-200), max(0, health-10), uid))
                    elif ev == "car_crash" and car and not car_broken:
                        c.execute("UPDATE players SET car_broken=1, health=? WHERE user_id=?", (max(0, health-15), uid))
            conn.commit(); conn.close()
        except Exception as e: print("Random Event Error:", e)
        await asyncio.sleep(1800)

async def background_tasks():
    asyncio.create_task(regen_job())
    asyncio.create_task(age_job())
    asyncio.create_task(interest_job())
    asyncio.create_task(random_event_job())

# ============================================================
# 🚀 main
# ============================================================
def main():
    init_db()
    
    proxy_url = None
    common_ports = [10809, 10808, 7890, 2080, 8080, 1080]
    
    import socket
    for port in common_ports:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                proxy_url = f"http://127.0.0.1:{port}"
                print(f"🌐 فیلترشکن روی پورت {port} پیدا شد!")
                break
        except (ConnectionRefusedError, TimeoutError, OSError):
            continue

    async def post_init(application: Application):
        await background_tasks()

    builder = Application.builder().token(TOKEN).post_init(post_init)
    
    if proxy_url:
        builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)
    else:
        print("⚠️ هیچ فیلترشکنی روی سیستم پیدا نشد!")
        
    app = builder.build()

    commands = [("start", start), ("me", me), ("work", work), ("daily", daily),
        ("job", job), ("edu", edu), ("finish_edu", finish_edu), ("bank", bank),
        ("loan", loan), ("shop", shop), ("food", food), ("fun", fun),
        ("hospital", hospital), ("fight", fight), ("garage", garage),
        ("friend", make_friend), ("friends", my_friends), ("myhome", go_myhome),
        ("visit", visit_home), ("supermarket", supermarket),
        ("give", give), ("top", top), ("delete", delete),
        ("jail", jail_status), ("trial", request_trial)]
    
    for cmd, fn in commands: app.add_handler(CommandHandler(cmd, fn))

    app.add_handler(CallbackQueryHandler(gender_choice, pattern="^gender_"))
    app.add_handler(CallbackQueryHandler(job_choice, pattern="^job_"))
    app.add_handler(CallbackQueryHandler(edu_choice, pattern="^edu_"))
    app.add_handler(CallbackQueryHandler(bank_choice, pattern="^bank_"))
    app.add_handler(CallbackQueryHandler(loan_choice, pattern="^loan_"))
    app.add_handler(CallbackQueryHandler(shop_choice, pattern="^(house_|car_)"))
    app.add_handler(CallbackQueryHandler(food_choice, pattern="^food_"))
    app.add_handler(CallbackQueryHandler(fun_choice, pattern="^fun_"))
    app.add_handler(CallbackQueryHandler(hospital_choice, pattern="^hosp_"))
    app.add_handler(CallbackQueryHandler(garage_choice, pattern="^repair_"))
    app.add_handler(CallbackQueryHandler(vote, pattern="^vote_"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^admin_"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("✅ ربات روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()