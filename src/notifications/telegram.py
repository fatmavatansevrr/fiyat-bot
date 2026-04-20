"""
Telegram notification service.
Sends price drop alerts and daily run summaries.
"""
import asyncio
import httpx
from datetime import datetime

from src.utils.logger import logger
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def _send(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("[telegram] Token or chat_id missing in .env — skipping")
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{BASE_URL}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
            )
            if r.status_code == 200:
                return True
            logger.warning(f"[telegram] API error {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"[telegram] Send failed: {e}")
        return False


async def send_alert(
    product: dict,
    retailer: str,
    old_price: float,
    new_price: float,
    discount_pct: float,
    url: str,
    title: str,
) -> bool:
    retailer_emoji = {
        "trendyol": "🛍",
        "amazon": "📦",
        "migros": "🛒",
        "carrefour": "🏪",
        "gurmar": "🏬",
    }.get(retailer, "🔔")

    msg = (
        f"{retailer_emoji} <b>FİYAT DÜŞTÜ!</b>\n\n"
        f"<b>{product['brand']} {product['model']}"
        f"{' ' + product['variant'] if product.get('variant') else ''}</b>\n"
        f"🏷 {title[:80]}\n\n"
        f"💰 <s>{old_price:.2f} TL</s>  →  <b>{new_price:.2f} TL</b>\n"
        f"📉 <b>%{discount_pct:.1f} indirim</b>\n\n"
        f"🏪 {retailer.capitalize()}\n"
        f"🔗 <a href='{url}'>Ürüne git</a>"
    )
    ok = await _send(msg)
    if ok:
        logger.info(f"[telegram] Alert sent: {product['brand']} {product['model']} -{discount_pct:.1f}%")
    return ok


async def send_summary(run_id: str, stats: dict, retailer_details: list[dict]):
    """Daily run summary — sent after all retailers are done."""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    lines = [
        f"📊 <b>Günlük Özet</b> — {now}\n",
        f"✅ Kontrol: {stats['checked']}  eşleşti: {stats['matched']}",
        f"🔔 Alert: {stats['alerts_sent']}  hata: {stats['failed']}\n",
    ]

    for rd in retailer_details:
        icon = "✅" if rd["failed"] == 0 else "⚠️"
        lines.append(
            f"{icon} {rd['retailer'].capitalize()}: "
            f"{rd['matched']}/{rd['checked']} eşleşti"
            + (f", {rd['alerts_sent']} alert" if rd['alerts_sent'] else "")
        )

    if stats["alerts_sent"] == 0:
        lines.append("\n💤 Bugün eşik aşan ürün yok.")

    await _send("\n".join(lines))


async def test_connection() -> bool:
    """Send a test message to verify bot token and chat_id are correct."""
    ok = await _send("✅ Price Monitor bağlantısı başarılı!")
    return ok
