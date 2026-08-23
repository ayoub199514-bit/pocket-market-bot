"""
signal_engine.py
يدمج المؤشرات الفنية ليعطي إشارة اتجاه نهائية: صعود / هبوط / محايد
مع نسبة "ثقة" تقريبية بناءً على عدد المؤشرات المتوافقة.

تنبيه: هذه إشارة احتمالية وليست توصية مالية أو ضمانًا لنتيجة الصفقة.
"""

import pandas as pd
from indicators import add_all_indicators


def generate_signal(df: pd.DataFrame) -> dict:
    """
    يأخذ DataFrame يحتوي على open/high/low/close
    ويعيد قاموسًا بالنتيجة: الاتجاه، نسبة الثقة، وتفاصيل كل مؤشر.
    """
    data = add_all_indicators(df)
    last = data.iloc[-1]

    votes = []  # كل مؤشر يصوّت: 1 = صعود، -1 = هبوط، 0 = محايد
    details = {}

    # 1) اتجاه المتوسطات المتحركة
    if last["ema_fast"] > last["ema_slow"]:
        votes.append(1)
        details["EMA (9/21)"] = "صعود 📈"
    else:
        votes.append(-1)
        details["EMA (9/21)"] = "هبوط 📉"

    # 2) RSI
    if last["rsi"] > 55:
        votes.append(1)
        details["RSI"] = f"صعود 📈 ({last['rsi']:.1f})"
    elif last["rsi"] < 45:
        votes.append(-1)
        details["RSI"] = f"هبوط 📉 ({last['rsi']:.1f})"
    else:
        votes.append(0)
        details["RSI"] = f"محايد ⚪ ({last['rsi']:.1f})"

    # 3) MACD histogram
    if last["macd_hist"] > 0:
        votes.append(1)
        details["MACD"] = "صعود 📈"
    else:
        votes.append(-1)
        details["MACD"] = "هبوط 📉"

    # 4) ADX — يخبرنا فقط إذا كان هناك اتجاه قوي أم لا (لا يصوّت على الاتجاه)
    trend_strength = "قوي 💪" if last["adx"] > 25 else "ضعيف / تذبذب ⚠️"
    details["ADX (قوة الاتجاه)"] = f"{trend_strength} ({last['adx']:.1f})"

    score = sum(votes)
    if score >= 2:
        direction = "صعود 📈 (شراء/CALL)"
    elif score <= -2:
        direction = "هبوط 📉 (بيع/PUT)"
    else:
        direction = "محايد ⚪ (لا إشارة واضحة)"

    confidence = round(abs(score) / len(votes) * 100)

    return {
        "direction": direction,
        "confidence": confidence,
        "adx_strength": last["adx"],
        "details": details,
        "last_close": last["close"],
        "last_time": data.index[-1],
        "data": data,
    }
