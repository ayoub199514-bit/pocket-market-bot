"""
data_fetch.py
جلب بيانات الأسعار (OHLC) من مصدر مالي عام (Yahoo Finance عبر yfinance).

ملاحظة مهمة:
Pocket Option لا توفر API عامة للمطورين، لذلك هذا البوت يستخدم بيانات
من مصدر خارجي مستقل (Yahoo Finance) لنفس نوع الأصول (فوركس، عملات رقمية، ذهب...).
الأسعار قريبة جدًا من Pocket Option لكن قد تختلف ببضع نقاط (spread مختلف).
"""

import pandas as pd
import yfinance as yf

# خريطة أسماء مبسطة إلى رموز Yahoo Finance
SYMBOL_MAP = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "XAU/USD (ذهب)": "GC=F",
    "US Oil (نفط)": "CL=F",
}

# الفريمات الزمنية المتاحة وربطها بإعدادات yfinance (interval, period)
TIMEFRAME_MAP = {
    "1 دقيقة": ("1m", "5d"),
    "5 دقائق": ("5m", "1mo"),
    "15 دقيقة": ("15m", "1mo"),
    "1 ساعة": ("1h", "3mo"),
    "1 يوم": ("1d", "1y"),
}

# فريم أعلى يُستخدم كتأكيد إضافي (Multi-Timeframe Confirmation) لكل فريم أساسي
HIGHER_TIMEFRAME_MAP = {
    "1 دقيقة": "5 دقائق",
    "5 دقائق": "15 دقيقة",
    "15 دقيقة": "1 ساعة",
    "1 ساعة": "1 يوم",
    "1 يوم": None,  # لا يوجد فريم أعلى منطقي هنا ضمن القائمة
}

# كل كم ثانية نتحقق (خفيف) من ظهور شمعة جديدة في وضع "تحليل عند إغلاق كل شمعة"
# القيمة أصغر من مدة الشمعة نفسها حتى لا تفوتنا لحظة إغلاقها
CANDLE_CHECK_INTERVAL_SECONDS = {
    "1 دقيقة": 5,
    "5 دقائق": 15,
    "15 دقيقة": 30,
    "1 ساعة": 60,
    "1 يوم": 300,
}


def _download(ticker: str, interval: str, period: str) -> pd.DataFrame:
    raw = yf.download(
        tickers=ticker,
        interval=interval,
        period=period,
        progress=False,
        auto_adjust=True,
    )

    if raw.empty:
        raise RuntimeError(
            "لم يتم استرجاع أي بيانات. تحقق من الاتصال بالإنترنت أو جرّب فريمًا زمنيًا آخر."
        )

    # yfinance أحيانًا يعيد أعمدة متعددة المستويات (MultiIndex) — نبسّطها
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )[["open", "high", "low", "close", "volume"]]

    return df.dropna()


def fetch_ohlc(symbol_label: str, timeframe_label: str) -> pd.DataFrame:
    """
    يجلب بيانات الشموع لرمز وفريم زمني معينين.
    يعيد DataFrame بأعمدة: open, high, low, close, volume (index = وقت الشمعة)
    """
    if symbol_label not in SYMBOL_MAP:
        raise ValueError(f"رمز غير معروف: {symbol_label}")
    if timeframe_label not in TIMEFRAME_MAP:
        raise ValueError(f"فريم زمني غير معروف: {timeframe_label}")

    ticker = SYMBOL_MAP[symbol_label]
    interval, period = TIMEFRAME_MAP[timeframe_label]
    return _download(ticker, interval, period)


def fetch_higher_timeframe_ohlc(symbol_label: str, timeframe_label: str):
    """
    يجلب بيانات فريم زمني أعلى لاستخدامها كتأكيد إضافي للإشارة.
    يعيد None بهدوء (بدون رفع استثناء) إذا تعذر الجلب أو لا يوجد فريم أعلى مناسب،
    لأن هذا تأكيد اختياري وليس أساسيًا لعمل التحليل.
    """
    higher_label = HIGHER_TIMEFRAME_MAP.get(timeframe_label)
    if higher_label is None:
        return None, None
    try:
        return fetch_ohlc(symbol_label, higher_label), higher_label
    except Exception:
        return None, higher_label
