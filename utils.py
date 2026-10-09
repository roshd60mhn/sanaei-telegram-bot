def gb(n: int | float) -> str:
    return f"{n / 1024**3:.2f} GB"

def usage_text(inbound, client):
    up = int(client.get("up") or 0)
    down = int(client.get("down") or 0)
    total = int(client.get("total") or 0)
    used = up + down
    limit = total
    if limit > 0:
        percent = min(100, used / limit * 100)
        remain = max(0, limit - used)
        quota = f"\n💾 حجم مجاز: {gb(limit)}\n📉 باقی‌مانده: {gb(remain)}\n📈 مصرف: {percent:.1f}%"
    else:
        quota = "\n💾 حجم مجاز: نامحدود"
    return (
        "📊 گزارش مصرف شما\n\n"
        f"🔌 پورت: {inbound.get('port', '-') }\n"
        f"📡 پروتکل: {inbound.get('protocol', '-') }\n\n"
        f"⬆️ آپلود: {gb(up)}\n"
        f"⬇️ دانلود: {gb(down)}\n"
        f"📦 مجموع: {gb(used)}"
        f"{quota}"
    )
