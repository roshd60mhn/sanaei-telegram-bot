import aiosqlite

from config import config


async def init_db():
    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                client_email TEXT,
                telegram_username TEXT,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                volume_gb INTEGER NOT NULL,
                price INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                plan_gb INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting_payment',
                receipt_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                plan_id INTEGER,
                service_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL UNIQUE,
                telegram_id INTEGER NOT NULL,
                inbound_id INTEGER,
                name TEXT NOT NULL,
                port INTEGER NOT NULL UNIQUE,
                rewrite_address TEXT NOT NULL,
                rewrite_port INTEGER NOT NULL,
                plan_gb INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # تنظیمات ربات
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
        """, (
            "support_username",
            "imogang",
        ))

        await db.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
        """, (
            "help_text",
            "📖 <b>راهنما</b>\\n\\n"
            "برای خرید سرویس، گزینه «🛒 خرید سرویس» را انتخاب کنید.\\n"
            "برای مشاهده سرویس‌ها، وارد «📦 سرویس‌های من» شوید.\\n"
            "برای مشاهده سفارش‌ها، «💳 سفارش‌های من» را انتخاب کنید.\\n"
            "برای تمدید یا تغییر پلن، از بخش سرویس‌های من اقدام کنید."
        ))

        # پلن‌های پیش‌فرض
        cursor = await db.execute("""
            SELECT COUNT(*)
            FROM plans
        """)
        plans_count = (await cursor.fetchone())[0]

        if plans_count == 0:
            await db.execute("""
                INSERT INTO plans (
                    name,
                    volume_gb,
                    price,
                    active
                )
                VALUES (?, ?, ?, 1)
            """, (
                "500GB",
                500,
                config.plan_500_price,
            ))

            await db.execute("""
                INSERT INTO plans (
                    name,
                    volume_gb,
                    price,
                    active
                )
                VALUES (?, ?, ?, 1)
            """, (
                "1000GB",
                1000,
                config.plan_1000_price,
            ))

        await db.commit()


# =========================================================
# USERS
# =========================================================

async def get_user(telegram_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = ?
        """, (telegram_id,))

        return await cursor.fetchone()


async def set_client(telegram_id: int, client_email: str):
    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            INSERT INTO users (
                telegram_id,
                client_email
            )
            VALUES (?, ?)
            ON CONFLICT(telegram_id)
            DO UPDATE SET client_email = excluded.client_email
        """, (
            telegram_id,
            client_email,
        ))

        await db.commit()


async def set_telegram_username(
    telegram_id: int,
    telegram_username: str | None,
    first_name: str | None,
    last_name: str | None,
):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("""
            INSERT INTO users (
                telegram_id,
                telegram_username,
                first_name,
                last_name
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id)
            DO UPDATE SET
                telegram_username = excluded.telegram_username,
                first_name = excluded.first_name,
                last_name = excluded.last_name
        """, (
            telegram_id,
            telegram_username,
            first_name,
            last_name,
        ))

        await db.commit()


# =========================================================
# PLANS
# =========================================================

async def create_plan(
    name: str,
    volume_gb: int,
    price: int,
):
    async with aiosqlite.connect(config.db_path) as db:

        cursor = await db.execute("""
            INSERT INTO plans (
                name,
                volume_gb,
                price,
                active
            )
            VALUES (?, ?, ?, 1)
        """, (
            name,
            volume_gb,
            price,
        ))

        await db.commit()

        return cursor.lastrowid


async def get_plan(plan_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM plans
            WHERE id = ?
        """, (plan_id,))

        return await cursor.fetchone()


async def get_active_plans():
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM plans
            WHERE active = 1
            ORDER BY volume_gb ASC, id ASC
        """)

        return await cursor.fetchall()


async def get_all_plans():
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM plans
            ORDER BY volume_gb ASC, id ASC
        """)

        return await cursor.fetchall()


async def update_plan(
    plan_id: int,
    name: str,
    volume_gb: int,
    price: int,
):
    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            UPDATE plans
            SET name = ?,
                volume_gb = ?,
                price = ?
            WHERE id = ?
        """, (
            name,
            volume_gb,
            price,
            plan_id,
        ))

        await db.commit()


async def set_plan_status(
    plan_id: int,
    active: bool,
):
    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            UPDATE plans
            SET active = ?
            WHERE id = ?
        """, (
            1 if active else 0,
            plan_id,
        ))

        await db.commit()


async def delete_plan(plan_id: int):
    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            DELETE FROM plans
            WHERE id = ?
        """, (plan_id,))

        await db.commit()


# =========================================================
# ORDERS
# =========================================================

async def create_order(
    telegram_id: int,
    plan_gb: int,
    amount: int,
    plan_id: int | None = None,
):
    async with aiosqlite.connect(config.db_path) as db:

        cursor = await db.execute("""
            INSERT INTO orders (
                telegram_id,
                plan_gb,
                amount,
                status,
                plan_id
            )
            VALUES (?, ?, ?, 'waiting_payment', ?)
        """, (
            telegram_id,
            plan_gb,
            amount,
            plan_id,
        ))

        await db.commit()

        return cursor.lastrowid


async def set_receipt(
    order_id: int,
    receipt_file_id: str,
):
    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            UPDATE orders
            SET receipt_file_id = ?,
                status = 'waiting_approval'
            WHERE id = ?
        """, (
            receipt_file_id,
            order_id,
        ))

        await db.commit()


async def get_order(order_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM orders
            WHERE id = ?
        """, (order_id,))

        return await cursor.fetchone()


async def approve_order(order_id: int):
    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            UPDATE orders
            SET status = 'approved',
                approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (order_id,))

        await db.commit()

async def set_order_status(
    order_id: int,
    status: str,
):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("""
            UPDATE orders
            SET status = ?
            WHERE id = ?
        """, (
            status,
            order_id,
        ))

        await db.commit()


async def reject_order(order_id: int):
    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            UPDATE orders
            SET status = 'rejected'
            WHERE id = ?
        """, (order_id,))

        await db.commit()


async def get_latest_waiting_order(telegram_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM orders
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (telegram_id,))

        return await cursor.fetchone()


async def get_latest_approved_order(telegram_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM orders
            WHERE telegram_id = ?
              AND status = 'approved'
            ORDER BY id DESC
            LIMIT 1
        """, (telegram_id,))

        return await cursor.fetchone()

async def create_renewal_order(
    telegram_id: int,
    service_id: int,
    plan_id: int,
    plan_gb: int,
    amount: int,
):
    async with aiosqlite.connect(config.db_path) as db:
        cursor = await db.execute("""
            INSERT INTO orders (
                telegram_id,
                plan_gb,
                amount,
                status,
                plan_id,
                service_id
            )
            VALUES (?, ?, ?, 'waiting_payment', ?, ?)
        """, (
            telegram_id,
            plan_gb,
            amount,
            plan_id,
            service_id,
        ))

        await db.commit()
        return cursor.lastrowid


# =========================================================
# SERVICES
# =========================================================

async def create_service(
    order_id: int,
    telegram_id: int,
    inbound_id: int,
    name: str,
    port: int,
    rewrite_address: str,
    rewrite_port: int,
    plan_gb: int,
):
    async with aiosqlite.connect(config.db_path) as db:

        cursor = await db.execute("""
            INSERT INTO services (
                order_id,
                telegram_id,
                inbound_id,
                name,
                port,
                rewrite_address,
                rewrite_port,
                plan_gb,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """, (
            order_id,
            telegram_id,
            inbound_id,
            name,
            port,
            rewrite_address,
            rewrite_port,
            plan_gb,
        ))

        await db.execute("""
            UPDATE orders
            SET status = 'service_created'
            WHERE id = ?
        """, (order_id,))

        await db.commit()

        return cursor.lastrowid

async def update_service_plan(
    service_id: int,
    plan_gb: int,
):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("""
            UPDATE services
            SET plan_gb = ?
            WHERE id = ?
        """, (
            plan_gb,
            service_id,
        ))

        await db.commit()

async def get_service_by_port(
    telegram_id: int,
    port: int,
):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM services
            WHERE telegram_id = ?
              AND port = ?
              AND status = 'active'
            LIMIT 1
        """, (
            telegram_id,
            port,
        ))

        return await cursor.fetchone()


async def get_user_services(telegram_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM services
            WHERE telegram_id = ?
              AND status != 'deleted'
            ORDER BY id DESC
        """, (telegram_id,))

        return await cursor.fetchall()


async def get_all_services(limit: int = 100):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM services
            WHERE status != 'deleted'
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        return await cursor.fetchall()


async def get_service_by_id(service_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM services
            WHERE id = ?
        """, (service_id,))

        return await cursor.fetchone()


async def set_service_status(
    service_id: int,
    status: str,
):
    allowed_statuses = {
        "active",
        "disabled",
        "deleted",
    }

    if status not in allowed_statuses:
        raise ValueError("Invalid service status")

    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            UPDATE services
            SET status = ?
            WHERE id = ?
        """, (
            status,
            service_id,
        ))

        await db.commit()


async def mark_service_deleted(service_id: int):
    await set_service_status(
        service_id,
        "deleted",
    )


async def mark_order_service_created(
    order_id: int,
    inbound_id: int,
):
    async with aiosqlite.connect(config.db_path) as db:

        await db.execute("""
            UPDATE orders
            SET status = 'service_created'
            WHERE id = ?
        """, (order_id,))

        await db.commit()


# =========================================================
# ADMIN / STATS
# =========================================================

async def get_admin_stats():
    async with aiosqlite.connect(config.db_path) as db:

        cursor = await db.execute("""
            SELECT COUNT(DISTINCT telegram_id)
            FROM orders
        """)

        users = (await cursor.fetchone())[0]

        cursor = await db.execute("""
            SELECT COUNT(*)
            FROM orders
        """)

        orders = (await cursor.fetchone())[0]

        cursor = await db.execute("""
            SELECT COUNT(*)
            FROM orders
            WHERE status = 'waiting_approval'
        """)

        pending = (await cursor.fetchone())[0]

        cursor = await db.execute("""
            SELECT COUNT(*)
            FROM services
            WHERE status = 'active'
        """)

        services = (await cursor.fetchone())[0]

        cursor = await db.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM orders
            WHERE status = 'service_created'
        """)

        revenue = (await cursor.fetchone())[0]

        cursor = await db.execute("""
            SELECT COALESCE(SUM(plan_gb), 0)
            FROM orders
            WHERE status = 'service_created'
        """)

        sold_gb = (await cursor.fetchone())[0]

        cursor = await db.execute("""
            SELECT COUNT(*)
            FROM plans
            WHERE active = 1
        """)

        active_plans = (await cursor.fetchone())[0]

        return {
            "users": users,
            "orders": orders,
            "pending": pending,
            "services": services,
            "revenue": revenue,
            "sold_gb": sold_gb,
            "active_plans": active_plans,
        }


async def get_pending_orders(limit: int = 20):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM orders
            WHERE status = 'waiting_approval'
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        return await cursor.fetchall()


async def get_recent_orders(limit: int = 20):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM orders
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        return await cursor.fetchall()


async def get_user_orders(telegram_id: int, limit: int = 20):
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM orders
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (telegram_id, limit))

        return await cursor.fetchall()


async def get_setting(key: str, default: str = ""):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.commit()

        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()

        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))

        await db.commit()


async def get_users_with_services():
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT
                u.telegram_id,
                u.telegram_username,
                s.id AS service_id,
                s.name AS service_name,
                s.port,
                s.plan_gb,
                s.status
            FROM users u
            LEFT JOIN services s
                ON s.telegram_id = u.telegram_id
                AND s.status != 'deleted'

            UNION

            SELECT
                s.telegram_id,
                NULL AS telegram_username,
                s.id AS service_id,
                s.name AS service_name,
                s.port,
                s.plan_gb,
                s.status
            FROM services s
            WHERE s.status != 'deleted'
              AND NOT EXISTS (
                  SELECT 1
                  FROM users u
                  WHERE u.telegram_id = s.telegram_id
              )

            ORDER BY telegram_id DESC, service_id DESC
        """)

        return await cursor.fetchall()

async def disable_user_services(telegram_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("""
            UPDATE services
            SET status = 'disabled'
            WHERE telegram_id = ?
              AND status != 'deleted'
        """, (telegram_id,))
        await db.commit()

async def delete_user_services(telegram_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("""
            UPDATE services
            SET status = 'deleted'
            WHERE telegram_id = ?
        """, (telegram_id,))
        await db.commit()
