import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import config
from database import (
    init_db,
    create_order,
    create_renewal_order,
    get_order,
    set_receipt,
    approve_order,
    set_order_status,
    reject_order,
    create_service,
    update_service_plan,
    get_service_by_port,
    get_user_services,
    get_all_services,
    get_service_by_id,
    set_service_status,
    mark_service_deleted,
    get_admin_stats,
    get_pending_orders,
    get_recent_orders,
    get_user_orders,
    create_plan,
    get_active_plans,
    get_plan,
    get_all_plans,
    update_plan,
    set_plan_status,
    delete_plan,
    get_setting,
    set_setting,
    set_telegram_username,
    disable_user_services,
    delete_user_services,
    get_users_with_services,
)
from sanaei import SanaeiAPI


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


bot = Bot(
    token=config.bot_token,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    ),
)

dp = Dispatcher()
sanaei = SanaeiAPI()


# =========================================================
# FSM
# =========================================================

class ServiceStates(StatesGroup):
    waiting_name = State()
    waiting_port = State()
    waiting_address = State()
    waiting_destination_port = State()
    waiting_confirmation = State()


class PlanStates(StatesGroup):
    waiting_name = State()
    waiting_volume = State()
    waiting_price = State()
    editing_name = State()
    editing_volume = State()
    editing_price = State()


class SettingsStates(StatesGroup):
    waiting_support = State()
    waiting_help = State()


# =========================================================
# Helpers
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


async def user_reply_keyboard():
    keyboard = [
        [
            KeyboardButton(text="🛒 خرید سرویس"),
            KeyboardButton(text="📦 سرویس‌های من"),
        ],
        [
            KeyboardButton(text="💳 سفارش‌های من"),
            KeyboardButton(text="📞 پشتیبانی"),
        ],
        [
            KeyboardButton(text="ℹ️ راهنما"),
            KeyboardButton(text="🔽 بستن منو")

        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )
async def admin_reply_keyboard():
    keyboard = [
        [
            KeyboardButton(text="🛒 خرید سرویس"),
            KeyboardButton(text="📦 سرویس‌های من"),
        ],
        [
            KeyboardButton(text="💳 سفارش‌های من"),
            KeyboardButton(text="📞 پشتیبانی"),
        ],
        [
            KeyboardButton(text="ℹ️ راهنما"),
            KeyboardButton(text="⌨️ منو"),

        ],
        [
            KeyboardButton(text="⚙️ مدیریت"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )

async def main_keyboard(user_id: int | None = None):
    buttons = [
        [
            InlineKeyboardButton(
                text="🛒 خرید سرویس",
                callback_data="menu:buy",
            )
        ],
        [
            InlineKeyboardButton(
                text="📦 سرویس‌های من",
                callback_data="my_services",
            )
        ],
        [
            InlineKeyboardButton(
                text="💳 سفارش‌های من",
                callback_data="menu:orders",
            )
        ],
        [
            InlineKeyboardButton(
                text="📞 پشتیبانی",
                callback_data="menu:support",
            ),
            InlineKeyboardButton(
                text="ℹ️ راهنما",
                callback_data="menu:help",
            ),
        ],
    ]

    if user_id is not None and is_admin(user_id):
        buttons.append([
            InlineKeyboardButton(
                text="⚙️ مدیریت",
                callback_data="admin:menu",
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 آمار",
                    callback_data="admin:stats",
                ),
                InlineKeyboardButton(
                    text="💳 پرداخت‌های در انتظار",
                    callback_data="admin:pending",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📦 سرویس‌ها",
                    callback_data="admin:services",
                ),
            ],
            [
                 InlineKeyboardButton(
                     text="💰 مدیریت پلن‌ها",
                    callback_data="admin:plans"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👥 سفارش‌های اخیر",
                    callback_data="admin:orders",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 بروزرسانی",
                    callback_data="admin:refresh",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ بستن",
                    callback_data="admin:close",
                ),
            ],
        ]
    )


def service_admin_keyboard(service):
    service_id = int(service["id"])
    status = service["status"]

    if status == "active":
        toggle_text = "🔴 غیرفعال کردن"
        toggle_action = f"service:disable:{service_id}"
    else:
        toggle_text = "🟢 فعال کردن"
        toggle_action = f"service:enable:{service_id}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 مصرف",
                    callback_data=f"service:usage:{service_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=toggle_action,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 حذف سرویس",
                    callback_data=f"service:delete:{service_id}",
                ),
            ],
        ]
    )


def service_delete_confirm_keyboard(service_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ بله، حذف شود",
                    callback_data=f"service:delete_confirm:{service_id}",
                ),
                InlineKeyboardButton(
                    text="❌ لغو",
                    callback_data="service:delete_cancel",
                ),
            ]
        ]
    )


def payment_admin_keyboard(order_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ تأیید پرداخت",
                    callback_data=f"payment:approve:{order_id}",
                ),
                InlineKeyboardButton(
                    text="❌ رد پرداخت",
                    callback_data=f"payment:reject:{order_id}",
                ),
            ]
        ]
    )


def create_service_keyboard(order_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚙️ ساخت سرویس",
                    callback_data=f"create_service:{order_id}",
                ),
            ],
        ]
    )


def format_bytes(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 0

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    size = float(value)

    for unit in units:
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024

    return f"{size:.2f} TB"


def format_service(service):
    status_map = {
        "active": "🟢 فعال",
        "disabled": "🔴 غیرفعال",
        "deleted": "⚫ حذف شده",
    }

    status = status_map.get(
        service["status"],
        service["status"],
    )

    return (
        f"📦 <b>{service['name']}</b>\n"
        f"🆔 شناسه سرویس: <code>{service['id']}</code>\n"
        f"👤 کاربر: <code>{service['telegram_id']}</code>\n"
        f"🔌 پورت: <code>{service['port']}</code>\n"
        f"🎯 مقصد: <code>{service['rewrite_address']}:{service['rewrite_port']}</code>\n"
        f"📦 حجم: <b>{service['plan_gb']}GB</b>\n"
        f"📌 وضعیت: {status}"
    )


async def get_inbound_usage(port: int):
    inbound = await sanaei.find_inbound_by_port(port)

    if not inbound:
        return None

    up = inbound.get("up", 0) or 0
    down = inbound.get("down", 0) or 0
    total = inbound.get("total", 0) or 0

    try:
        up = int(up)
    except (TypeError, ValueError):
        up = 0

    try:
        down = int(down)
    except (TypeError, ValueError):
        down = 0

    try:
        total = int(total)
    except (TypeError, ValueError):
        total = 0

    used = up + down

    return {
        "up": up,
        "down": down,
        "used": used,
        "total": total,
    }


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def start_handler(message: Message):
    await set_telegram_username(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )

    text = (
        "👋 <b>خوش آمدید</b>\n\n"
        "از منوی زیر می‌توانید سرویس خود را خریداری و مدیریت کنید."
    )

    if is_admin(message.from_user.id):
        keyboard = await admin_reply_keyboard()
    else:
        keyboard = await user_reply_keyboard()

    await message.answer(
        text,
        reply_markup=keyboard,
    )


# =========================================================
@dp.message(F.text == "🛒 خرید سرویس")
async def reply_buy_handler(message: Message):
    plans = await get_active_plans()

    if not plans:
        await message.answer(
            "❌ در حال حاضر پلنی برای خرید وجود ندارد."
        )
        return

    buttons = []

    for plan in plans:
        buttons.append([
            InlineKeyboardButton(
                text=(
                    f"🛒 {plan['name']} "
                    f"— {plan['price']:,} تومان"
                ),
                callback_data=f"buy:{plan['id']}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 بازگشت به منوی اصلی",
            callback_data="menu:back",
        )
    ])

    await message.answer(
        "📦 <b>پلن مورد نظر را انتخاب کنید:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )

@dp.callback_query(F.data == "menu:buy")
async def menu_buy_handler(callback: CallbackQuery):
    plans = await get_active_plans()

    if not plans:
        await callback.answer(
            "❌ در حال حاضر پلنی برای خرید وجود ندارد.",
            show_alert=True,
        )
        return

    buttons = []

    for plan in plans:
        buttons.append([
            InlineKeyboardButton(
                text=(
                    f"🛒 {plan['name']} "
                    f"— {plan['price']:,} تومان"
                ),
                callback_data=f"buy:{plan['id']}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 بازگشت به منوی اصلی",
            callback_data="menu:back",
        )
    ])

    await callback.message.edit_text(
        "🛒 <b>خرید سرویس</b>\n\n"
        "پلن موردنظر خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )
    await callback.answer()


@dp.callback_query(F.data == "menu:back")
async def menu_back_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "👋 <b>خوش آمدید</b>\n\n"
        "از منوی زیر می‌توانید سرویس خود را خریداری و مدیریت کنید.",
        reply_markup=await main_keyboard(callback.from_user.id),
    )
    await callback.answer()


@dp.callback_query(F.data == "menu:orders")
async def menu_orders_handler(callback: CallbackQuery):
    orders = await get_user_orders(callback.from_user.id)

    if not orders:
        await callback.message.edit_text(
            "💳 <b>سفارش‌های من</b>\n\n"
            "هنوز سفارشی ثبت نکرده‌اید.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="🔙 بازگشت به منوی اصلی",
                        callback_data="menu:back",
                    )
                ]]
            ),
        )
        await callback.answer()
        return

    status_names = {
        "waiting_payment": "⏳ در انتظار پرداخت",
        "waiting_approval": "🔎 در انتظار تأیید",
        "approved": "✅ تأیید شده",
        "service_created": "🟢 سرویس ساخته شد",
        "renewed": "🔄 تمدید شد",
        "rejected": "❌ رد شده",
    }

    lines = ["💳 <b>سفارش‌های من</b>", ""]

    for order in orders:
        status = status_names.get(
            order["status"],
            order["status"],
        )

        lines.append(
            f"🧾 سفارش <code>#{order['id']}</code>\n"
            f"📦 حجم: <b>{order['plan_gb']}GB</b>\n"
            f"💰 مبلغ: <b>{order['amount']:,} تومان</b>\n"
            f"📌 وضعیت: {status}\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔙 بازگشت به منوی اصلی",
                    callback_data="menu:back",
                )
            ]]
        ),
    )
    await callback.answer()


@dp.callback_query(F.data == "menu:support")
async def menu_support_handler(callback: CallbackQuery):
    support = await get_setting("support_username", "imogang")
    support = support.strip()

    if support.startswith("@"):
        support_url = f"https://t.me/{support[1:]}"
    elif support.startswith("http://") or support.startswith("https://"):
        support_url = support
    else:
        support_url = f"https://t.me/{support}"

    await callback.message.edit_text(
        "📞 <b>پشتیبانی</b>\\n\\n"
        "برای ارتباط با پشتیبانی روی دکمه زیر بزنید:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 ارتباط با پشتیبانی",
                        url=support_url,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 بازگشت به منوی اصلی",
                        callback_data="menu:back",
                    )
                ],
            ]
        ),
    )
    await callback.answer()


@dp.callback_query(F.data == "menu:help")
async def menu_help_handler(callback: CallbackQuery):
    help_text = await get_setting(
        "help_text",
        "📖 <b>راهنما</b>\\n\\n"
        "برای خرید سرویس، گزینه «🛒 خرید سرویس» را انتخاب کنید.\\n"
        "برای مشاهده سرویس‌ها، وارد «📦 سرویس‌های من» شوید.\\n"
        "برای مشاهده سفارش‌ها، «💳 سفارش‌های من» را انتخاب کنید.\\n"
        "برای تمدید یا تغییر پلن، از بخش سرویس‌های من اقدام کنید."
    )

    await callback.message.edit_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔙 بازگشت به منوی اصلی",
                    callback_data="menu:back",
                )
            ]]
        ),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:menu")
async def admin_menu_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ دسترسی غیرمجاز",
            show_alert=True,
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 مدیریت پلن‌ها",
                    callback_data="admin:plans",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧾 مدیریت سفارش‌ها",
                    callback_data="admin:orders",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🖥 مدیریت سرویس‌ها",
                    callback_data="admin:services",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 کاربران",
                    callback_data="admin:users",
                ),
                InlineKeyboardButton(
                    text="📊 آمار",
                    callback_data="admin:stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📞 تنظیم پشتیبانی",
                    callback_data="admin:support",
                ),
                InlineKeyboardButton(
                    text="ℹ️ تنظیم راهنما",
                    callback_data="admin:help",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="menu:back",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "⚙️ <b>مدیریت ربات</b>\n\n"
        "بخش موردنظر را انتخاب کنید:",
        reply_markup=keyboard,
    )
    await callback.answer()


# BUY
# =========================================================

@dp.callback_query(F.data.startswith("buy:"))
async def buy_handler(callback: CallbackQuery):
    try:
        plan_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            "خطا در انتخاب پلن",
            show_alert=True,
        )
        return

    plan = await get_plan(plan_id)

    if not plan:
        await callback.answer(
            "پلن پیدا نشد.",
            show_alert=True,
        )
        return

    if not plan["active"]:
        await callback.answer(
            "این پلن در حال حاضر غیرفعال است.",
            show_alert=True,
        )
        return

    plan_gb = plan["volume_gb"]
    amount = plan["price"]

    order_id = await create_order(
        telegram_id=callback.from_user.id,
        plan_gb=plan_gb,
        amount=amount,
        plan_id=plan_id,
    )

    text = (
        f"🛒 <b>سفارش جدید</b>\n\n"
        f"📦 پلن: <b>{plan['name']}</b>\n"
        f"📊 حجم: <b>{plan_gb}GB</b>\n"
        f"💰 مبلغ: <b>{amount:,}</b> تومان\n\n"
        f"💳 لطفاً مبلغ را به کارت زیر واریز کنید:\n"
        f"<code>{config.card_number}</code>\n\n"
        f"🧾 سپس تصویر رسید را همینجا ارسال کنید.\n\n"
        f"شماره سفارش: <code>#{order_id}</code>"
    )

    await callback.message.answer(text)

    await callback.answer()


# =========================================================
# RECEIPT
# =========================================================

@dp.message(F.photo)
async def receipt_handler(message: Message):
    order = await get_order_by_latest_waiting(message.from_user.id)

    if not order:
        await message.answer(
            "❌ سفارش در انتظار پرداختی برای شما پیدا نشد."
        )
        return

    if order["status"] != "waiting_payment":
        await message.answer(
            "❌ این سفارش در وضعیت دریافت رسید نیست."
        )
        return

    photo = message.photo[-1]

    await set_receipt(
        order["id"],
        photo.file_id,
    )

    await message.answer(
        "✅ رسید دریافت شد.\n"
        "⏳ لطفاً منتظر تأیید پرداخت توسط ادمین باشید."
    )

    user = message.from_user
    full_name = " ".join(
        part for part in [user.first_name, user.last_name] if part
    )
    username = f"@{user.username}" if user.username else "ندارد"

    admin_text = (
        "💳 <b>رسید پرداخت جدید</b>\n\n"
        f"🧾 سفارش: <code>#{order['id']}</code>\n"
        f"👤 نام: <b>{full_name}</b>\n"
        f"🔗 نام کاربری: {username}\n"
        f"🆔 آیدی عددی: <code>{user.id}</code>\n"
        f"📦 پلن: <b>{order['plan_gb']}GB</b>\n"
        f"💰 مبلغ: <b>{order['amount']:,}</b> تومان"
    )

    for admin_id in config.admin_ids:
        try:
            await bot.send_photo(
                admin_id,
                photo.file_id,
                caption=admin_text,
                reply_markup=payment_admin_keyboard(
                    order["id"]
                ),
            )
        except Exception as exc:
            logger.error(
                "Failed to send receipt to admin %s: %s",
                admin_id,
                exc,
            )


async def get_latest_waiting_order_for_user(telegram_id: int):
    from database import get_latest_waiting_order

    return await get_latest_waiting_order(telegram_id)


async def get_order_by_latest_waiting(telegram_id: int):
    return await get_latest_waiting_order_for_user(telegram_id)


# =========================================================
# PAYMENT APPROVE
# =========================================================

@dp.callback_query(F.data.startswith("payment:approve:"))
async def approve_payment_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        order_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer(
            "شناسه سفارش نامعتبر است",
            show_alert=True,
        )
        return

    order = await get_order(order_id)

    if not order:
        await callback.answer(
            "سفارش پیدا نشد",
            show_alert=True,
        )
        return

    if order["status"] != "waiting_approval":
        await callback.answer(
            "این سفارش قبلاً بررسی شده است",
            show_alert=True,
        )
        return

    await approve_order(order_id)

    await callback.answer(
        "پرداخت تأیید شد"
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.message.answer(
        f"✅ پرداخت سفارش <code>#{order_id}</code> تأیید شد."
    )

    if order["service_id"]:
        await callback.message.answer(
            "🔄 سفارش تمدید شناسایی شد."
        )
        service = await get_service_by_id(order["service_id"])

        if not service:
            await callback.message.answer(
                "❌ سرویس مربوط به این سفارش پیدا نشد."
            )
            return
        plan = await get_plan(order["plan_id"])

        if not plan:
            await callback.message.answer(
                "❌ پلن جدید این سفارش پیدا نشد."
            )
            return
        total_bytes = plan["volume_gb"] * 1024 * 1024 * 1024

        try:
            await sanaei.update_inbound_total(
                service["inbound_id"],
                total_bytes,
            )
        except Exception as exc:
            logger.error(
                "Failed to update renewal quota: %s",
                exc,
            )
            await callback.message.answer(
                "❌ تغییر حجم سرویس در پنل انجام نشد. "
                "سرویس بدون تغییر باقی ماند."
            )
            return

        await update_service_plan(
            service["id"],
            plan["volume_gb"],
        )
        await set_order_status(
            order_id,
            "renewed",
        )

        await callback.message.answer(
            f"✅ <b>تمدید سرویس با موفقیت انجام شد.</b>\n\n"
            f"📦 سرویس: <b>{service['name']}</b>\n"
            f"📊 حجم جدید: <b>{plan['volume_gb']}GB</b>\n"
            f"💰 مبلغ: <b>{order['amount']:,}</b> تومان"
        )


        return

    try:
        await bot.send_message(
            order["telegram_id"],
            (
                "✅ <b>پرداخت شما تأیید شد.</b>\n\n"
                f"📦 پلن: <b>{order['plan_gb']}GB</b>\n"
                f"💰 مبلغ: <b>{order['amount']:,}</b> تومان\n\n"
                "حالا می‌توانید سرویس خود را بسازید."
            ),
            reply_markup=create_service_keyboard(order_id),
        )
    except Exception as exc:
        logger.error(
            "Failed to notify user: %s",
            exc,
        )


# =========================================================
# PAYMENT REJECT
# =========================================================

@dp.callback_query(F.data.startswith("payment:reject:"))
async def reject_payment_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        order_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer(
            "شناسه سفارش نامعتبر است",
            show_alert=True,
        )
        return

    order = await get_order(order_id)

    if not order:
        await callback.answer(
            "سفارش پیدا نشد",
            show_alert=True,
        )
        return

    if order["status"] != "waiting_approval":
        await callback.answer(
            "این سفارش قبلاً بررسی شده است",
            show_alert=True,
        )
        return

    await reject_order(order_id)

    await callback.answer(
        "پرداخت رد شد"
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.message.answer(
        f"❌ پرداخت سفارش <code>#{order_id}</code> رد شد."
    )

    try:
        await bot.send_message(
            order["telegram_id"],
            (
                "❌ <b>پرداخت شما تأیید نشد.</b>\n\n"
                f"شماره سفارش: <code>#{order_id}</code>\n"
                "در صورت نیاز، دوباره سفارش ثبت کنید."
            ),
        )
    except Exception as exc:
        logger.error(
            "Failed to notify user: %s",
            exc,
        )


# =========================================================
# CREATE SERVICE
# =========================================================

@dp.callback_query(F.data.startswith("create_service:"))
async def create_service_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    try:
        order_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            "سفارش نامعتبر است",
            show_alert=True,
        )
        return

    order = await get_order(order_id)

    if not order:
        await callback.answer(
            "سفارش پیدا نشد",
            show_alert=True,
        )
        return

    if order["telegram_id"] != callback.from_user.id:
        await callback.answer(
            "این سفارش متعلق به شما نیست",
            show_alert=True,
        )
        return

    if order["status"] != "approved":
        await callback.answer(
            "این سفارش آماده ساخت سرویس نیست",
            show_alert=True,
        )
        return

    await state.clear()

    await state.update_data(
        order_id=order_id,
        plan_gb=order["plan_gb"],
    )

    await state.set_state(
        ServiceStates.waiting_name
    )

    await callback.message.answer(
        "✏️ <b>مرحله ۱ از ۴</b>\n\n"
        "یک نام برای سرویس وارد کنید.\n\n"
        "مثال:\n"
        "<code>my-server</code>"
    )

    await callback.answer()


@dp.message(ServiceStates.waiting_name)
async def service_name_handler(
    message: Message,
    state: FSMContext,
):
    name = message.text.strip()

    if not name:
        await message.answer(
            "❌ نام سرویس نمی‌تواند خالی باشد."
        )
        return

    if len(name) > 100:
        await message.answer(
            "❌ نام سرویس بیش از حد طولانی است."
        )
        return

    await state.update_data(
        name=name
    )

    await state.set_state(
        ServiceStates.waiting_port
    )

    await message.answer(
        "🔌 <b>مرحله ۲ از ۴</b>\n\n"
        "پورت ورودی سرویس را وارد کنید.\n\n"
        "مثال:\n"
        "<code>8578</code>"
    )


@dp.message(ServiceStates.waiting_port)
async def service_port_handler(
    message: Message,
    state: FSMContext,
):
    try:
        port = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer(
            "❌ پورت باید عدد باشد."
        )
        return

    if port < 1 or port > 65535:
        await message.answer(
            "❌ پورت باید بین 1 تا 65535 باشد."
        )
        return

    existing = await sanaei.find_inbound_by_port(
        port
    )

    if existing:
        await message.answer(
            "❌ این پورت در پنل استفاده شده است.\n"
            "یک پورت دیگر وارد کنید."
        )
        return

    await state.update_data(
        port=port
    )

    await state.set_state(
        ServiceStates.waiting_address
    )

    await message.answer(
        "🎯 <b>مرحله ۳ از ۴</b>\n\n"
        "آدرس مقصد را وارد کنید.\n\n"
        "مثال:\n"
        "<code>206.1.100.59</code>"
    )


@dp.message(ServiceStates.waiting_address)
async def service_address_handler(
    message: Message,
    state: FSMContext,
):
    address = message.text.strip()

    if not address:
        await message.answer(
            "❌ آدرس مقصد نمی‌تواند خالی باشد."
        )
        return

    if len(address) > 255:
        await message.answer(
            "❌ آدرس واردشده معتبر نیست."
        )
        return

    await state.update_data(
        rewrite_address=address
    )

    await state.set_state(
        ServiceStates.waiting_destination_port
    )

    await message.answer(
        "🔢 <b>مرحله ۴ از ۴</b>\n\n"
        "پورت مقصد را وارد کنید.\n\n"
        "مثال:\n"
        "<code>8578</code>"
    )


@dp.message(ServiceStates.waiting_destination_port)
async def service_destination_port_handler(
    message: Message,
    state: FSMContext,
):
    try:
        destination_port = int(
            message.text.strip()
        )
    except (ValueError, AttributeError):
        await message.answer(
            "❌ پورت مقصد باید عدد باشد."
        )
        return

    if destination_port < 1 or destination_port > 65535:
        await message.answer(
            "❌ پورت مقصد باید بین 1 تا 65535 باشد."
        )
        return

    await state.update_data(
        rewrite_port=destination_port
    )

    data = await state.get_data()

    text = (
        "📋 <b>بررسی اطلاعات سرویس</b>\n\n"
        f"📦 نام: <code>{data['name']}</code>\n"
        f"🔌 پورت ورودی: <code>{data['port']}</code>\n"
        f"🎯 مقصد: <code>{data['rewrite_address']}:{destination_port}</code>\n"
        f"📦 حجم: <b>{data['plan_gb']}GB</b>\n\n"
        "اگر اطلاعات درست است، پیام زیر را ارسال کنید:\n"
        "<b>تایید</b>"
    )

    await state.set_state(
        ServiceStates.waiting_confirmation
    )

    await message.answer(text)


@dp.message(ServiceStates.waiting_confirmation)
async def service_confirmation_handler(
    message: Message,
    state: FSMContext,
):
    answer = message.text.strip().lower()

    if answer not in (
        "تایید",
        "تایید میکنم",
        "تأیید",
        "yes",
        "ok",
    ):
        await message.answer(
            "برای ادامه عبارت <b>تایید</b> را ارسال کنید."
        )
        return

    data = await state.get_data()

    order_id = int(data["order_id"])
    plan_gb = int(data["plan_gb"])
    name = data["name"]
    port = int(data["port"])
    rewrite_address = data["rewrite_address"]
    rewrite_port = int(data["rewrite_port"])

    total_bytes = plan_gb * 1024 * 1024 * 1024

    await message.answer(
        "⏳ در حال ساخت سرویس در پنل..."
    )

    try:
        existing = await sanaei.find_inbound_by_port(
            port
        )

        if existing:
            await message.answer(
                "❌ این پورت در پنل استفاده شده است."
            )
            return

        result = await sanaei.create_tunnel(
            remark=name,
            port=port,
            rewrite_address=rewrite_address,
            rewrite_port=rewrite_port,
            total_bytes=total_bytes,
        )

        # بعد از ساخت، inbound واقعی را از پنل پیدا می‌کنیم
        # تا ID واقعی آن در دیتابیس ذخیره شود.
        created_inbound = await sanaei.find_inbound_by_port(
            port
        )

        inbound_id = 0

        if created_inbound:
            try:
                inbound_id = int(
                    created_inbound.get("id", 0)
                )
            except (TypeError, ValueError):
                inbound_id = 0

        # اگر پنل ID را داخل نتیجه ایجاد داده باشد
        if not inbound_id:
            obj = result.get("obj")

            if isinstance(obj, dict):
                try:
                    inbound_id = int(
                        obj.get("id")
                        or obj.get("_id")
                        or 0
                    )
                except (TypeError, ValueError):
                    inbound_id = 0

            elif isinstance(obj, int):
                inbound_id = obj

            elif isinstance(obj, str):
                try:
                    inbound_id = int(obj)
                except ValueError:
                    inbound_id = 0

        await create_service(
            order_id=order_id,
            telegram_id=message.from_user.id,
            inbound_id=inbound_id,
            name=name,
            port=port,
            rewrite_address=rewrite_address,
            rewrite_port=rewrite_port,
            plan_gb=plan_gb,
        )

        await state.clear()

        await message.answer(
            "✅ <b>سرویس با موفقیت ساخته شد.</b>\n\n"
            f"📦 نام: <code>{name}</code>\n"
            f"🔌 پورت: <code>{port}</code>\n"
            f"🎯 مقصد: <code>{rewrite_address}:{rewrite_port}</code>\n"
            f"📦 حجم: <b>{plan_gb}GB</b>\n\n"
            "برای مدیریت سرویس یا مشاهده راهنما از دکمه‌های زیر استفاده کنید.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📦 سرویس‌های من",
                            callback_data="my_services",
                        ),
                        InlineKeyboardButton(
                            text="ℹ️ راهنما",
                            callback_data="menu:help",
                        ),
                    ]
                ]
            ),
        )

    except Exception as exc:
        logger.exception(
            "Failed to create service"
        )

        await message.answer(
            "❌ خطا در ساخت سرویس.\n\n"
            f"<code>{str(exc)}</code>"
        )


# =========================================================
# MY SERVICES
# =========================================================

@dp.callback_query(F.data == "my_services")
async def my_services_handler(
    callback: CallbackQuery,
):
    services = await get_user_services(
        callback.from_user.id
    )

    if not services:
        await callback.message.answer(
            "📦 شما هنوز سرویسی ندارید."
        )
        await callback.answer()
        return

    for service in services:
        status_map = {
            "active": "🟢 فعال",
            "disabled": "🔴 غیرفعال",
        }

        status = status_map.get(
            service["status"],
            service["status"],
        )

        text = (
            f"📦 <b>{service['name']}</b>\n\n"
            f"🔌 پورت: <code>{service['port']}</code>\n"
            f"🎯 مقصد: <code>{service['rewrite_address']}:{service['rewrite_port']}</code>\n"
            f"📦 حجم: <b>{service['plan_gb']}GB</b>\n"
            f"📌 وضعیت: {status}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 مشاهده مصرف",
                        callback_data=f"user:usage:{service['id']}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 تمدید / تغییر پلن",
                        callback_data=f"service:renew:{service['id']}",
                    ),
                ],
            ]
        )

        await callback.message.answer(
            text,
            reply_markup=keyboard,
        )

    await callback.answer()

# =========================================================
# REPLY KEYBOARD HANDLERS
# =========================================================

@dp.message(F.text == "📦 سرویس‌های من")
async def reply_my_services_handler(message: Message):
    services = await get_user_services(message.from_user.id)

    if not services:
        await message.answer("📦 شما هنوز سرویسی ندارید.")
        return

    for service in services:
        status_map = {
            "active": "🟢 فعال",
            "disabled": "🔴 غیرفعال",
        }

        status = status_map.get(
            service["status"],
            service["status"],
        )

        text = (
            f"📦 <b>{service['name']}</b>\n\n"
            f"🔌 پورت: <code>{service['port']}</code>\n"
            f"🎯 مقصد: <code>{service['rewrite_address']}:{service['rewrite_port']}</code>\n"
            f"📦 حجم: <b>{service['plan_gb']}GB</b>\n"
            f"📌 وضعیت: {status}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 مشاهده مصرف",
                        callback_data=f"user:usage:{service['id']}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 تمدید / تغییر پلن",
                        callback_data=f"service:renew:{service['id']}",
                    ),
                ],
            ]
        )

        await message.answer(
            text,
            reply_markup=keyboard,
        )


@dp.message(F.text == "💳 سفارش‌های من")
async def reply_orders_handler(message: Message):
    orders = await get_user_orders(message.from_user.id)

    if not orders:
        await message.answer(
            "💳 <b>سفارش‌های من</b>\n\n"
            "هنوز سفارشی ثبت نکرده‌اید."
        )
        return

    status_names = {
        "waiting_payment": "⏳ در انتظار پرداخت",
        "waiting_approval": "🔎 در انتظار تأیید",
        "approved": "✅ تأیید شده",
        "service_created": "🟢 سرویس ساخته شد",
        "renewed": "🔄 تمدید شد",
        "rejected": "❌ رد شده",
    }

    lines = ["💳 <b>سفارش‌های من</b>", ""]

    for order in orders:
        status = status_names.get(
            order["status"],
            order["status"],
        )

        lines.append(
            f"🧾 سفارش <code>#{order['id']}</code>\n"
            f"📦 حجم: <b>{order['plan_gb']}GB</b>\n"
            f"💰 مبلغ: <b>{order['amount']:,} تومان</b>\n"
            f"📌 وضعیت: {status}\n"
        )

    await message.answer("\n".join(lines))


@dp.message(F.text == "📞 پشتیبانی")
async def reply_support_handler(message: Message):
    support = await get_setting(
        "support_username",
        "imogang",
    )

    support = support.strip()

    if support.startswith("@"):
        support_url = f"https://t.me/{support[1:]}"
    elif support.startswith("http://") or support.startswith("https://"):
        support_url = support
    else:
        support_url = f"https://t.me/{support}"

    await message.answer(
        "📞 <b>پشتیبانی</b>\n\n"
        "برای ارتباط با پشتیبانی روی دکمه زیر بزنید:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 ارتباط با پشتیبانی",
                        url=support_url,
                    )
                ]
            ]
        ),
    )


@dp.message(F.text == "⌨️ منو")
async def reply_menu_handler(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "⚙️ منوی مدیریت:",
            reply_markup=await admin_reply_keyboard(),
        )
    else:
        await message.answer(
            "⌨️ منوی اصلی:",
            reply_markup=await user_reply_keyboard(),
        )


@dp.message(F.text == "🔽 بستن منو")
async def close_menu_handler(message: Message):
    await message.answer(
        "⌨️ منو بسته شد.",
        reply_markup=ReplyKeyboardRemove(),
    )

async def reply_menu_handler(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "⚙️ منوی مدیریت:",
            reply_markup=await admin_reply_keyboard(),
        )
    else:
        await message.answer(
            "⌨️ منوی اصلی:",
            reply_markup=await user_reply_keyboard(),
        )


@dp.message(F.text == "ℹ️ راهنما")
async def reply_help_handler(message: Message):
    help_text = await get_setting(
        "help_text",
        "📖 <b>راهنما</b>\n\n"
        "برای خرید سرویس، گزینه «🛒 خرید سرویس» را انتخاب کنید.\n"
        "برای مشاهده سرویس‌ها، وارد «📦 سرویس‌های من» شوید.\n"
        "برای مشاهده سفارش‌ها، «💳 سفارش‌های من» را انتخاب کنید.\n"
        "برای تمدید یا تغییر پلن، از بخش سرویس‌های من اقدام کنید."
    )

    await message.answer(help_text)


@dp.message(F.text == "⚙️ مدیریت")
async def reply_admin_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ دسترسی غیرمجاز")
        return

    await message.answer(
        "⚙️ <b>مدیریت ربات</b>\n\n"
        "بخش موردنظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📦 مدیریت پلن‌ها",
                        callback_data="admin:plans",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🧾 مدیریت سفارش‌ها",
                        callback_data="admin:orders",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🖥 مدیریت سرویس‌ها",
                        callback_data="admin:services",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👥 کاربران",
                        callback_data="admin:users",
                    ),
                    InlineKeyboardButton(
                        text="📊 آمار",
                        callback_data="admin:stats",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📞 تنظیم پشتیبانی",
                        callback_data="admin:support",
                    ),
                    InlineKeyboardButton(
                        text="ℹ️ تنظیم راهنما",
                        callback_data="admin:help",
                    ),
                ],
            ]
        ),
    )

# =========================================================
# SERVICE RENEW
# =========================================================

@dp.callback_query(F.data.startswith("service:renew:"))
async def service_renew_handler(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[2])

    service = await get_service_by_id(service_id)

    if not service:
        await callback.answer("❌ سرویس پیدا نشد.", show_alert=True)
        return

    if service["telegram_id"] != callback.from_user.id:
        await callback.answer("❌ این سرویس متعلق به شما نیست.", show_alert=True)
        return

    if service["status"] == "deleted":
        await callback.answer("❌ این سرویس حذف شده است.", show_alert=True)
        return

    plans = await get_active_plans()

    if not plans:
        await callback.answer(
            "❌ در حال حاضر هیچ پلن فعالی وجود ندارد.",
            show_alert=True,
        )
        return

    buttons = []

    for plan in plans:
        buttons.append([
            InlineKeyboardButton(
                text=f"🔄 {plan['name']} — {plan['price']:,} تومان",
                callback_data=f"renew_plan:{service_id}:{plan['id']}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="❌ انصراف",
            callback_data="renew_cancel",
        )
    ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

    await callback.message.answer(
        f"🔄 <b>تمدید / تغییر پلن</b>\n\n"
        f"📦 سرویس: <b>{service['name']}</b>\n"
        f"📊 پلن فعلی: <b>{service['plan_gb']}GB</b>\n\n"
        f"پلن جدید را انتخاب کنید:",
        reply_markup=keyboard,
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("renew_plan:"))
async def renew_plan_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    service_id = int(parts[1])
    plan_id = int(parts[2])
    service = await get_service_by_id(service_id)
    if not service:
        await callback.answer("❌ سرویس پیدا نشد.", show_alert=True)
        return
    if service["telegram_id"] != callback.from_user.id:
        await callback.answer("❌ این سرویس متعلق به شما نیست.", show_alert=True)
        return
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("❌ پلن انتخاب‌شده پیدا نشد.", show_alert=True)
        return
    if not plan["active"]:
        await callback.answer("❌ این پلن دیگر فعال نیست.", show_alert=True)
        return
    order_id = await create_renewal_order(
        telegram_id=callback.from_user.id,
        service_id=service_id,
        plan_id=plan_id,
        plan_gb=plan["volume_gb"],
        amount=plan["price"],
    )
    await callback.message.answer(
        f"🔄 <b>سفارش تمدید سرویس</b>\n\n"
        f"📦 سرویس: <b>{service['name']}</b>\n"
        f"📊 پلن جدید: <b>{plan['name']}</b>\n"
        f"💰 مبلغ: <b>{plan['price']:,} تومان</b>\n"
        f"🧾 شماره سفارش: <code>#{order_id}</code>\n\n"
        f"💳 شماره کارت: <code>{config.card_number}</code>\n"
        "💳 مبلغ را به کارت اعلام‌شده واریز کنید و سپس رسید پرداخت را ارسال کنید."
    )



@dp.callback_query(F.data == "renew_cancel")
async def renew_cancel_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "❌ تمدید سرویس لغو شد."
    )
    await callback.answer()


# =========================================================
# USAGE COMMAND
# =========================================================

@dp.message(Command("usage"))
async def usage_handler(message: Message):
    parts = message.text.split()

    if len(parts) != 2:
        await message.answer(
            "استفاده صحیح:\n"
            "<code>/usage PORT</code>\n\n"
            "مثال:\n"
            "<code>/usage 8578</code>"
        )
        return

    try:
        port = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ پورت باید عدد باشد."
        )
        return

    service = await get_service_by_port(
        message.from_user.id,
        port,
    )

    if not service:
        await message.answer(
            "❌ سرویسی با این پورت برای شما پیدا نشد."
        )
        return

    usage = await get_inbound_usage(
        port
    )

    if not usage:
        await message.answer(
            "❌ سرویس در پنل پیدا نشد."
        )
        return

    text = (
        f"📊 <b>مصرف سرویس {service['name']}</b>\n\n"
        f"🔌 پورت: <code>{port}</code>\n"
        f"⬆️ آپلود: <b>{format_bytes(usage['up'])}</b>\n"
        f"⬇️ دانلود: <b>{format_bytes(usage['down'])}</b>\n"
        f"📊 مصرف کل: <b>{format_bytes(usage['used'])}</b>\n"
    )

    if usage["total"] > 0:
        text += (
            f"📦 سقف: <b>{format_bytes(usage['total'])}</b>\n"
        )

        remaining = max(
            usage["total"] - usage["used"],
            0,
        )

        text += (
            f"📌 باقی‌مانده: <b>{format_bytes(remaining)}</b>"
        )

    await message.answer(text)


# =========================================================
# ADMIN PANEL
# =========================================================

@dp.message(Command("admin"))
async def admin_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            "❌ دسترسی ندارید."
        )
        return

    await message.answer(
        "🛠 <b>پنل مدیریت</b>\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=admin_keyboard(),
    )


# =========================================================
# ADMIN USERS
# =========================================================

@dp.callback_query(F.data == "admin:users")
async def admin_users_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    rows = await get_users_with_services()

    if not rows:
        await callback.message.edit_text(
            "👥 هنوز کاربری ثبت نشده است.",
            reply_markup=admin_keyboard(),
        )
        await callback.answer()
        return

    users = {}

    for row in rows:
        telegram_id = row["telegram_id"]

        if telegram_id not in users:
            users[telegram_id] = {
                "username": row["telegram_username"],
                "services": [],
            }

        if row["service_id"]:
            users[telegram_id]["services"].append(row)

    text = "👥 <b>کاربران و سرویس‌ها</b>\n\n"

    for telegram_id, user in users.items():
        username = user["username"]

        if username:
            username_text = f"@{username}"
        else:
            username_text = "ندارد"

        text += (
            f"👤 <b>{username_text}</b>\n"
            f"🆔 آیدی عددی: <code>{telegram_id}</code>\n"
        )

        text += (
            f"🔴 خاموش کردن همه سرویس‌ها: "
            f"/disable_user_{telegram_id}\n"
            f"🗑️ حذف همه سرویس‌ها: "
            f"/delete_user_{telegram_id}\n"
        )

        if user["services"]:
            text += "📦 سرویس‌ها:\n"

            for service in user["services"]:
                status_map = {
                    "active": "🟢",
                    "disabled": "🔴",
                }

                status = status_map.get(
                    service["status"],
                    "⚫",
                )

                text += (
                    f"   {status} "
                    f"🔌 پورت: <code>{service['port']}</code> "
                    f"— {service['plan_gb']}GB\n"
                )
        else:
            text += "📦 سرویس: ندارد\n"

        text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=admin_keyboard(),
    )

    await callback.answer()

@dp.message(F.text.startswith("/disable_user_"))
async def disable_user_handler(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        telegram_id = int(message.text.split("_")[-1])
    except (ValueError, IndexError):
        await message.answer("شناسه کاربر نامعتبر است.")
        return

    await disable_user_services(telegram_id)

    await message.answer(
        f"🔴 تمام سرویس‌های کاربر <code>{telegram_id}</code> خاموش شدند."
    )


@dp.message(F.text.startswith("/delete_user_"))
async def delete_user_handler(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        telegram_id = int(message.text.split("_")[-1])
    except (ValueError, IndexError):
        await message.answer("شناسه کاربر نامعتبر است.")
        return

    await delete_user_services(telegram_id)

    await message.answer(
        f"🗑️ تمام سرویس‌های کاربر <code>{telegram_id}</code> حذف شدند."
    )

# =========================================================
# ADMIN STATS
# =========================================================

@dp.callback_query(F.data == "admin:stats")
async def admin_stats_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    stats = await get_admin_stats()

    text = (
        "📊 <b>آمار سیستم</b>\n\n"
        f"👥 کاربران: <b>{stats['users']}</b>\n"
        f"🧾 سفارش‌ها: <b>{stats['orders']}</b>\n"
        f"⏳ در انتظار تأیید: <b>{stats['pending']}</b>\n"
        f"📦 سرویس‌های فعال: <b>{stats['services']}</b>\n"
        f"💰 درآمد: <b>{stats['revenue']:,}</b> تومان\n"
        f"📦 حجم فروخته‌شده: <b>{stats['sold_gb']}GB</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=admin_keyboard(),
    )

    await callback.answer()


# =========================================================
# ADMIN PENDING PAYMENTS
# =========================================================

@dp.callback_query(F.data == "admin:pending")
async def admin_pending_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    orders = await get_pending_orders()

    if not orders:
        await callback.message.answer(
            "✅ پرداخت در انتظار تأیید وجود ندارد."
        )
        await callback.answer()
        return

    await callback.message.answer(
        f"⏳ <b>{len(orders)}</b> پرداخت در انتظار تأیید:"
    )

    for order in orders:
        text = (
            f"💳 <b>سفارش #{order['id']}</b>\n\n"
            f"👤 کاربر: <code>{order['telegram_id']}</code>\n"
            f"📦 پلن: <b>{order['plan_gb']}GB</b>\n"
            f"💰 مبلغ: <b>{order['amount']:,}</b> تومان"
        )

        if order["receipt_file_id"]:
            try:
                await callback.message.answer_photo(
                    order["receipt_file_id"],
                    caption=text,
                    reply_markup=payment_admin_keyboard(
                        order["id"]
                    ),
                )
            except Exception:
                await callback.message.answer(
                    text,
                    reply_markup=payment_admin_keyboard(
                        order["id"]
                    ),
                )
        else:
            await callback.message.answer(
                text,
                reply_markup=payment_admin_keyboard(
                    order["id"]
                ),
            )

    await callback.answer()


# =========================================================
# ADMIN SERVICES
# =========================================================

@dp.callback_query(F.data == "plan:add")
async def plan_add_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    await state.clear()
    await state.set_state(PlanStates.waiting_name)

    await callback.message.answer(
        "➕ <b>افزودن پلن</b>\n\n"
        "نام پلن را وارد کنید:\n"
        "مثال: <code>750GB</code>"
    )

    await callback.answer()


@dp.message(PlanStates.waiting_name)
async def plan_name_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    name = message.text.strip()

    if not name:
        await message.answer("❌ نام پلن نمی‌تواند خالی باشد.")
        return

    await state.update_data(name=name)
    await state.set_state(PlanStates.waiting_volume)

    await message.answer(
        "📦 حجم پلن را به GB وارد کنید:\n"
        "مثال: <code>750</code>"
    )


@dp.message(PlanStates.waiting_volume)
async def plan_volume_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    try:
        volume = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ حجم باید عدد باشد.\n"
            "مثال: <code>750</code>"
        )
        return

    if volume <= 0:
        await message.answer(
            "❌ حجم باید بیشتر از صفر باشد."
        )
        return

    await state.update_data(volume=volume)
    await state.set_state(PlanStates.waiting_price)

    await message.answer(
        "💰 قیمت پلن را به تومان وارد کنید:\n"
        "مثال: <code>700000</code>"
    )


@dp.message(PlanStates.waiting_price)
async def plan_price_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ قیمت باید عدد باشد.\n"
            "مثال: <code>700000</code>"
        )
        return

    if price <= 0:
        await message.answer(
            "❌ قیمت باید بیشتر از صفر باشد."
        )
        return

    data = await state.get_data()

    plan_id = await create_plan(
        name=data["name"],
        volume_gb=data["volume"],
        price=price,
    )

    await state.clear()

    await message.answer(
        "✅ <b>پلن با موفقیت ایجاد شد.</b>\n\n"
        f"📦 نام: <b>{data['name']}</b>\n"
        f"📊 حجم: <b>{data['volume']}GB</b>\n"
        f"💰 قیمت: <b>{price:,}</b> تومان\n"
        f"🆔 شناسه پلن: <code>{plan_id}</code>",
        reply_markup=admin_keyboard(),
    )


@dp.callback_query(F.data.startswith("plan:view:"))
async def plan_view_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        plan_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer(
            "شناسه پلن نامعتبر است.",
            show_alert=True,
        )
        return

    plan = await get_plan(plan_id)

    if not plan:
        await callback.answer(
            "پلن پیدا نشد.",
            show_alert=True,
        )
        return

    status = "🟢 فعال" if plan["active"] else "🔴 غیرفعال"

    buttons = []

    if plan["active"]:
        buttons.append([
            InlineKeyboardButton(
                text="🔴 غیرفعال کردن",
                callback_data=f"plan:disable:{plan_id}",
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="🟢 فعال کردن",
                callback_data=f"plan:enable:{plan_id}",
            )
        ])

    buttons.append([
       InlineKeyboardButton(
         text="✏️ ویرایش پلن",
         callback_data=f"plan:edit:{plan_id}",
       )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="🗑 حذف پلن",
            callback_data=f"plan:delete:{plan_id}",
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 لیست پلن‌ها",
            callback_data="admin:plans",
        )
    ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

    await callback.message.edit_text(
        "💰 <b>جزئیات پلن</b>\n\n"
        f"🆔 شناسه: <code>{plan['id']}</code>\n"
        f"📦 نام: <b>{plan['name']}</b>\n"
        f"📊 حجم: <b>{plan['volume_gb']}GB</b>\n"
        f"💵 قیمت: <b>{plan['price']:,}</b> تومان\n"
        f"📌 وضعیت: {status}",
        reply_markup=keyboard,
    )

    await callback.answer()

@dp.callback_query(F.data.startswith("plan:edit:"))
async def plan_edit_handler(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        plan_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer(
            "شناسه پلن نامعتبر است.",
            show_alert=True,
        )
        return

    plan = await get_plan(plan_id)

    if not plan:
        await callback.answer(
            "پلن پیدا نشد.",
            show_alert=True,
        )
        return

    await state.clear()
    await state.update_data(plan_id=plan_id)
    await state.set_state(PlanStates.editing_name)

    await callback.message.answer(
        "✏️ <b>ویرایش پلن</b>\n\n"
        f"نام فعلی: <b>{plan['name']}</b>\n\n"
        "نام جدید را وارد کنید:"
    )

    await callback.answer()


@dp.message(PlanStates.editing_name)
async def plan_edit_name_handler(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    name = message.text.strip()

    if not name:
        await message.answer(
            "❌ نام پلن نمی‌تواند خالی باشد."
        )
        return

    await state.update_data(name=name)
    await state.set_state(PlanStates.editing_volume)

    await message.answer(
        "📦 حجم جدید را به GB وارد کنید:"
    )


@dp.message(PlanStates.editing_volume)
async def plan_edit_volume_handler(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    try:
        volume = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ حجم باید عدد باشد."
        )
        return

    if volume <= 0:
        await message.answer(
            "❌ حجم باید بیشتر از صفر باشد."
        )
        return

    await state.update_data(volume=volume)
    await state.set_state(PlanStates.editing_price)

    await message.answer(
        "💰 قیمت جدید را به تومان وارد کنید:"
    )


@dp.message(PlanStates.editing_price)
async def plan_edit_price_handler(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ قیمت باید عدد باشد."
        )
        return

    if price <= 0:
        await message.answer(
            "❌ قیمت باید بیشتر از صفر باشد."
        )
        return

    data = await state.get_data()

    await update_plan(
        plan_id=data["plan_id"],
        name=data["name"],
        volume_gb=data["volume"],
        price=price,
    )

    await state.clear()

    await message.answer(
        "✅ <b>پلن با موفقیت ویرایش شد.</b>\n\n"
        f"📦 نام: <b>{data['name']}</b>\n"
        f"📊 حجم: <b>{data['volume']}GB</b>\n"
        f"💰 قیمت: <b>{price:,}</b> تومان",
        reply_markup=admin_keyboard(),
    )

@dp.callback_query(F.data.startswith("plan:enable:"))
async def plan_enable_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        plan_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer(
            "شناسه پلن نامعتبر است.",
            show_alert=True,
        )
        return

    plan = await get_plan(plan_id)

    if not plan:
        await callback.answer(
            "پلن پیدا نشد.",
            show_alert=True,
        )
        return

    await set_plan_status(plan_id, True)

    await callback.answer("✅ پلن فعال شد.")

    await admin_plans_handler(callback)


@dp.callback_query(F.data.startswith("plan:disable:"))
async def plan_disable_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        plan_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer(
            "شناسه پلن نامعتبر است.",
            show_alert=True,
        )
        return

    plan = await get_plan(plan_id)

    if not plan:
        await callback.answer(
            "پلن پیدا نشد.",
            show_alert=True,
        )
        return

    await set_plan_status(plan_id, False)

    await callback.answer("🔴 پلن غیرفعال شد.")

    await admin_plans_handler(callback)


@dp.callback_query(F.data.startswith("plan:delete:"))
async def plan_delete_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        plan_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer(
            "شناسه پلن نامعتبر است.",
            show_alert=True,
        )
        return

    plan = await get_plan(plan_id)

    if not plan:
        await callback.answer(
            "پلن پیدا نشد.",
            show_alert=True,
        )
        return

    await delete_plan(plan_id)

    await callback.answer("🗑 پلن حذف شد.")

    await admin_plans_handler(callback)

@dp.callback_query(F.data == "admin:support")
async def admin_support_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید", show_alert=True)
        return

    current = await get_setting("support_username", "imogang")

    await state.set_state(SettingsStates.waiting_support)

    await callback.message.edit_text(
        "📞 <b>تنظیم پشتیبانی</b>\\n\\n"
        f"مقدار فعلی: <code>{current}</code>\\n\\n"
        "یوزرنیم یا آیدی جدید پشتیبانی را ارسال کنید.\\n"
        "مثال: <code>imogang</code> یا <code>@imogang</code>"
    )

    await callback.answer()


@dp.message(SettingsStates.waiting_support)
async def save_support_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    value = message.text.strip()

    if not value:
        await message.answer("❌ مقدار نامعتبر است. دوباره ارسال کنید.")
        return

    await set_setting("support_username", value)
    await state.clear()

    await message.answer(
        f"✅ آیدی پشتیبانی ذخیره شد.\\n\\n"
        f"📞 <code>{value}</code>",
        reply_markup=await main_keyboard(message.from_user.id),
    )


@dp.callback_query(F.data == "admin:help")
async def admin_help_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید", show_alert=True)
        return

    current = await get_setting(
        "help_text",
        "📖 <b>راهنما</b>\\n\\n"
        "برای خرید سرویس، گزینه «🛒 خرید سرویس» را انتخاب کنید.\\n"
        "برای مشاهده سرویس‌ها، وارد «📦 سرویس‌های من» شوید.\\n"
        "برای مشاهده سفارش‌ها، «💳 سفارش‌های من» را انتخاب کنید.\\n"
        "برای تمدید یا تغییر پلن، از بخش سرویس‌های من اقدام کنید."
    )

    await state.set_state(SettingsStates.waiting_help)

    await callback.message.edit_text(
        "ℹ️ <b>تنظیم متن راهنما</b>\\n\\n"
        "متن فعلی:\\n\\n"
        f"{current}\\n\\n"
        "متن جدید را در یک پیام ارسال کنید."
    )

    await callback.answer()


@dp.message(SettingsStates.waiting_help)
async def save_help_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    value = message.text.strip()

    if not value:
        await message.answer("❌ متن خالی است. دوباره ارسال کنید.")
        return

    await set_setting("help_text", value)
    await state.clear()

    await message.answer(
        "✅ متن راهنما با موفقیت ذخیره شد.",
        reply_markup=await main_keyboard(message.from_user.id),
    )


@dp.callback_query(F.data == "admin:services")
@dp.callback_query(F.data == "admin:plans")
async def admin_plans_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    plans = await get_all_plans()

    if not plans:
        await callback.message.answer(
            "📦 هیچ پلنی ثبت نشده است."
        )
        await callback.answer()
        return

    buttons = []

    for plan in plans:
        status = "🟢" if plan["active"] else "🔴"

        buttons.append([
            InlineKeyboardButton(
                text=(
                    f"{status} {plan['name']} | "
                    f"{plan['volume_gb']}GB | "
                    f"{plan['price']:,} تومان"
                ),
                callback_data=f"plan:view:{plan['id']}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="➕ افزودن پلن",
            callback_data="plan:add",
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="🔄 بروزرسانی",
            callback_data="admin:plans",
        ),
        InlineKeyboardButton(
            text="🔙 پنل مدیریت",
            callback_data="admin:refresh",
        ),
    ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

    await callback.message.edit_text(
        "💰 <b>مدیریت پلن‌ها</b>\n\n"
        "پلن موردنظر را انتخاب کنید:",
        reply_markup=keyboard,
    )

    await callback.answer()

async def admin_services_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    services = await get_all_services()

    if not services:
        await callback.message.answer(
            "📦 هیچ سرویسی ثبت نشده است."
        )
        await callback.answer()
        return

    await callback.message.answer(
        f"📦 <b>{len(services)}</b> سرویس:"
    )

    for service in services:
        await callback.message.answer(
            format_service(service),
            reply_markup=service_admin_keyboard(
                service
            ),
        )

    await callback.answer()


@dp.callback_query(F.data.startswith("user:usage:"))
async def user_service_usage_handler(callback: CallbackQuery):
    try:
        service_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("شناسه سرویس نامعتبر است", show_alert=True)
        return

    service = await get_service_by_id(service_id)

    if not service or int(service["telegram_id"]) != callback.from_user.id:
        await callback.answer("سرویس پیدا نشد یا دسترسی ندارید", show_alert=True)
        return

    usage = await get_inbound_usage(service["port"])

    if not usage:
        await callback.answer("اطلاعات مصرف از پنل دریافت نشد", show_alert=True)
        return

    text = (
        f"📊 <b>مصرف سرویس شما</b>\n\n"
        f"📦 نام سرویس: <b>{service['name']}</b>\n"
        f"⬆️ آپلود: <b>{format_bytes(usage['up'])}</b>\n"
        f"⬇️ دانلود: <b>{format_bytes(usage['down'])}</b>\n"
        f"📊 مصرف کل: <b>{format_bytes(usage['used'])}</b>"
    )

    if usage["total"] > 0:
        remaining = max(usage["total"] - usage["used"], 0)
        text += (
            f"\n📦 حجم کل: <b>{format_bytes(usage['total'])}</b>"
            f"\n📌 حجم باقی‌مانده: <b>{format_bytes(remaining)}</b>"
        )

    await callback.message.answer(text)
    await callback.answer()


# =========================================================
# ADMIN SERVICE USAGE
# =========================================================

@dp.callback_query(
    F.data.startswith("service:usage:")
)
async def admin_service_usage_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        service_id = int(
            callback.data.split(":")[2]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "شناسه سرویس نامعتبر است",
            show_alert=True,
        )
        return

    service = await get_service_by_id(
        service_id
    )

    if not service:
        await callback.answer(
            "سرویس پیدا نشد",
            show_alert=True,
        )
        return

    usage = await get_inbound_usage(
        service["port"]
    )

    if not usage:
        await callback.message.answer(
            "❌ سرویس در پنل Sanaei پیدا نشد."
        )
        await callback.answer()
        return

    text = (
        f"📊 <b>مصرف سرویس</b>\n\n"
        f"📦 نام: <b>{service['name']}</b>\n"
        f"👤 کاربر: <code>{service['telegram_id']}</code>\n"
        f"🔌 پورت: <code>{service['port']}</code>\n\n"
        f"⬆️ آپلود: <b>{format_bytes(usage['up'])}</b>\n"
        f"⬇️ دانلود: <b>{format_bytes(usage['down'])}</b>\n"
        f"📊 مصرف کل: <b>{format_bytes(usage['used'])}</b>"
    )

    if usage["total"] > 0:
        remaining = max(
            usage["total"] - usage["used"],
            0,
        )

        text += (
            f"\n📦 سقف: <b>{format_bytes(usage['total'])}</b>"
            f"\n📌 باقی‌مانده: <b>{format_bytes(remaining)}</b>"
        )

    await callback.message.answer(
        text
    )

    await callback.answer()


# =========================================================
# ADMIN ENABLE
# =========================================================

@dp.callback_query(
    F.data.startswith("service:enable:")
)
async def admin_service_enable_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        service_id = int(
            callback.data.split(":")[2]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "شناسه سرویس نامعتبر است",
            show_alert=True,
        )
        return

    service = await get_service_by_id(
        service_id
    )

    if not service:
        await callback.answer(
            "سرویس پیدا نشد",
            show_alert=True,
        )
        return

    inbound_id = service["inbound_id"]

    if not inbound_id:
        inbound = await sanaei.find_inbound_by_port(
            service["port"]
        )

        if not inbound:
            await callback.answer(
                "سرویس در پنل پیدا نشد",
                show_alert=True,
            )
            return

        inbound_id = inbound.get("id")

    try:
        await sanaei.toggle_inbound(
            int(inbound_id),
            True,
        )

        await set_service_status(
            service_id,
            "active",
        )

        await callback.answer(
            "سرویس فعال شد"
        )

        await callback.message.edit_reply_markup(
            reply_markup=service_admin_keyboard(
                {
                    **dict(service),
                    "status": "active",
                }
            )
        )

    except Exception as exc:
        logger.exception(
            "Failed to enable service"
        )

        await callback.answer(
            f"خطا: {str(exc)}",
            show_alert=True,
        )


# =========================================================
# ADMIN DISABLE
# =========================================================

@dp.callback_query(
    F.data.startswith("service:disable:")
)
async def admin_service_disable_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        service_id = int(
            callback.data.split(":")[2]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "شناسه سرویس نامعتبر است",
            show_alert=True,
        )
        return

    service = await get_service_by_id(
        service_id
    )

    if not service:
        await callback.answer(
            "سرویس پیدا نشد",
            show_alert=True,
        )
        return

    inbound_id = service["inbound_id"]

    if not inbound_id:
        inbound = await sanaei.find_inbound_by_port(
            service["port"]
        )

        if not inbound:
            await callback.answer(
                "سرویس در پنل پیدا نشد",
                show_alert=True,
            )
            return

        inbound_id = inbound.get("id")

    try:
        await sanaei.toggle_inbound(
            int(inbound_id),
            False,
        )

        await set_service_status(
            service_id,
            "disabled",
        )

        await callback.answer(
            "سرویس غیرفعال شد"
        )

        await callback.message.edit_reply_markup(
            reply_markup=service_admin_keyboard(
                {
                    **dict(service),
                    "status": "disabled",
                }
            )
        )

    except Exception as exc:
        logger.exception(
            "Failed to disable service"
        )

        await callback.answer(
            f"خطا: {str(exc)}",
            show_alert=True,
        )


# =========================================================
# ADMIN DELETE REQUEST
# =========================================================

@dp.callback_query(
    F.data.startswith("service:delete:")
)
async def admin_service_delete_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        service_id = int(
            callback.data.split(":")[2]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "شناسه سرویس نامعتبر است",
            show_alert=True,
        )
        return

    service = await get_service_by_id(
        service_id
    )

    if not service:
        await callback.answer(
            "سرویس پیدا نشد",
            show_alert=True,
        )
        return

    await callback.message.answer(
        (
            "⚠️ <b>حذف سرویس</b>\n\n"
            f"📦 سرویس: <b>{service['name']}</b>\n"
            f"🔌 پورت: <code>{service['port']}</code>\n\n"
            "آیا مطمئن هستید؟"
        ),
        reply_markup=service_delete_confirm_keyboard(
            service_id
        ),
    )

    await callback.answer()


# =========================================================
# ADMIN DELETE CONFIRM
# =========================================================

@dp.callback_query(
    F.data.startswith("service:delete_confirm:")
)
async def admin_service_delete_confirm_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    try:
        service_id = int(
            callback.data.split(":")[2]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "شناسه سرویس نامعتبر است",
            show_alert=True,
        )
        return

    service = await get_service_by_id(
        service_id
    )

    if not service:
        await callback.answer(
            "سرویس پیدا نشد",
            show_alert=True,
        )
        return

    inbound_id = service["inbound_id"]

    try:
        if not inbound_id:
            inbound = await sanaei.find_inbound_by_port(
                service["port"]
            )

            if inbound:
                inbound_id = inbound.get("id")

        if inbound_id:
            await sanaei.delete_inbound(
                int(inbound_id)
            )

        await mark_service_deleted(
            service_id
        )

        await callback.message.edit_text(
            (
                "✅ <b>سرویس حذف شد.</b>\n\n"
                f"📦 {service['name']}\n"
                f"🔌 پورت: <code>{service['port']}</code>"
            )
        )

        await callback.answer(
            "سرویس حذف شد"
        )

        try:
            await bot.send_message(
                service["telegram_id"],
                (
                    "⚠️ <b>سرویس شما حذف شد.</b>\n\n"
                    f"📦 نام: <b>{service['name']}</b>\n"
                    f"🔌 پورت: <code>{service['port']}</code>"
                ),
            )
        except Exception:
            pass

    except Exception as exc:
        logger.exception(
            "Failed to delete service"
        )

        await callback.answer(
            f"خطا در حذف: {str(exc)}",
            show_alert=True,
        )


# =========================================================
# DELETE CANCEL
# =========================================================

@dp.callback_query(
    F.data == "service:delete_cancel"
)
async def admin_service_delete_cancel(
    callback: CallbackQuery,
):
    await callback.message.edit_text(
        "❌ حذف سرویس لغو شد."
    )

    await callback.answer()


# =========================================================
# ADMIN RECENT ORDERS
# =========================================================

@dp.callback_query(F.data == "admin:orders")
async def admin_orders_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    orders = await get_recent_orders()

    if not orders:
        await callback.message.answer(
            "🧾 سفارشی وجود ندارد."
        )
        await callback.answer()
        return

    for order in orders:
        text = (
            f"🧾 <b>سفارش #{order['id']}</b>\n"
            f"👤 کاربر: <code>{order['telegram_id']}</code>\n"
            f"📦 پلن: <b>{order['plan_gb']}GB</b>\n"
            f"💰 مبلغ: <b>{order['amount']:,}</b> تومان\n"
            f"📌 وضعیت: <code>{order['status']}</code>"
        )

        await callback.message.answer(
            text
        )

    await callback.answer()


# =========================================================
# ADMIN REFRESH
# =========================================================

@dp.callback_query(F.data == "admin:refresh")
async def admin_refresh_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    stats = await get_admin_stats()

    text = (
        "🔄 <b>پنل مدیریت</b>\n\n"
        f"👥 کاربران: <b>{stats['users']}</b>\n"
        f"🧾 سفارش‌ها: <b>{stats['orders']}</b>\n"
        f"⏳ در انتظار: <b>{stats['pending']}</b>\n"
        f"📦 سرویس‌های فعال: <b>{stats['services']}</b>\n"
        f"💰 درآمد: <b>{stats['revenue']:,}</b> تومان"
    )

    await callback.message.edit_text(
        text,
        reply_markup=admin_keyboard(),
    )

    await callback.answer(
        "بروزرسانی شد"
    )


# =========================================================
# ADMIN CLOSE
# =========================================================

@dp.callback_query(F.data == "admin:close")
async def admin_close_handler(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "دسترسی ندارید",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "✅ پنل مدیریت بسته شد."
    )

    await callback.answer()


# =========================================================
# ERROR HANDLER
# =========================================================

@dp.errors()
async def global_error_handler(event):
    logger.exception(
        "Unhandled bot error: %s",
        event.exception,
    )


# =========================================================
# MAIN
# =========================================================

async def main():
    await init_db()

    logger.info("Bot started")

    try:
        await dp.start_polling(bot)

    finally:
        await sanaei.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
