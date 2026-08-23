"""
signal_engine.py
يدمج المؤشرات الفنية (EMA, RSI, MACD, ADX, Bollinger, Stochastic, ATR)
مع تأكيد من فريم زمني أعلى، ليعطي إشارة اتجاه نهائية موزونة (Weighted)
مع نسبة "ثقة" ومستوى قوة الإشارة، ومستويات دعم/مقاومة تقريبية.

تنبيه: هذه إشارة احتمالية بناءً على تحليل فني تاريخي، وليست توصية مالية
ولا ضمانًا لنتيجة أي صفقة. الأداء السابق للمؤشرات لا يضمن نتائج مستقبلية.
"""

import pandas as pd
from indicators import add_all_indicators, support_resistance

# وزن كل مؤشر في النتيجة النهائية (كلما زاد الوزن زاد تأثيره على القرار)
WEIGHTS = {
    "ema_cross": 1.5,   # تقاطع EMA9/21 — الأهم
    "ema_trend": 1.0,   # موقع السعر من EMA50 (اتجاه عام)
    "rsi": 1.0,
    "macd": 1.0,
    "stochastic": 1.0,
    "bollinger": 0.75,
}
MAX_SCORE = sum(WEIGHTS.values())  # أقصى نتيجة ممكنة إذا اتفقت كل المؤشرات


def _higher_timeframe_bias(df_higher: pd.DataFrame) -> int:
    """
    يحدد اتجاه الفريم الأعلى (تأكيد إضافي) بناءً على تقاطع EMA9/21.
    يعيد 1 (صعود) / -1 (هبوط) / 0 (غير محدد).
    """
    if df_higher is None or df_higher.empty or len(df_higher) < 25:
        return 0
    data = add_all_indicators(df_higher)
    last = data.iloc[-1]
    if pd.isna(last["ema_fast"]) or pd.isna(last["ema_slow"]):
        return 0
    return 1 if last["ema_fast"] > last["ema_slow"] else -1


def generate_signal(df: pd.DataFrame, df_higher: pd.DataFrame = None) -> dict:
    """
    يأخذ DataFrame يحتوي على open/high/low/close (وبيانات فريم أعلى اختياريًا للتأكيد)
    ويعيد قاموسًا بالنتيجة: الاتجاه، نسبة الثقة، قوة الإشارة، التفاصيل، الدعم/المقاومة، وتحذيرات.
    """
    data = add_all_indicators(df)
    last = data.iloc[-1]

    votes = []      # (اسم, تصويت -1/0/1, وزن)
    details = {}
    warnings = []

    # 1) تقاطع EMA السريع/البطيء
    if last["ema_fast"] > last["ema_slow"]:
        votes.append(("ema_cross", 1, WEIGHTS["ema_cross"]))
        details["EMA (9/21)"] = "صعود 📈"
    else:
        votes.append(("ema_cross", -1, WEIGHTS["ema_cross"]))
        details["EMA (9/21)"] = "هبوط 📉"

    # 2) موقع السعر من EMA50 (فلتر الاتجاه العام)
    if pd.notna(last.get("ema_trend")):
        if last["close"] > last["ema_trend"]:
            votes.append(("ema_trend", 1, WEIGHTS["ema_trend"]))
            details["الاتجاه العام (EMA50)"] = "فوق المتوسط 📈"
        else:
            votes.append(("ema_trend", -1, WEIGHTS["ema_trend"]))
            details["الاتجاه العام (EMA50)"] = "تحت المتوسط 📉"

    # 3) RSI
    if last["rsi"] > 55:
        votes.append(("rsi", 1, WEIGHTS["rsi"]))
        details["RSI"] = f"صعود 📈 ({last['rsi']:.1f})"
    elif last["rsi"] < 45:
        votes.append(("rsi", -1, WEIGHTS["rsi"]))
        details["RSI"] = f"هبوط 📉 ({last['rsi']:.1f})"
    else:
        votes.append(("rsi", 0, WEIGHTS["rsi"]))
        details["RSI"] = f"محايد ⚪ ({last['rsi']:.1f})"

    if last["rsi"] > 70:
        warnings.append("RSI في منطقة تشبع شرائي (>70) — احتمال ارتداد.")
    elif last["rsi"] < 30:
        warnings.append("RSI في منطقة تشبع بيعي (<30) — احتمال ارتداد.")

    # 4) MACD histogram
    if last["macd_hist"] > 0:
        votes.append(("macd", 1, WEIGHTS["macd"]))
        details["MACD"] = "صعود 📈"
    else:
        votes.append(("macd", -1, WEIGHTS["macd"]))
        details["MACD"] = "هبوط 📉"

    # 5) Stochastic
    if pd.notna(last.get("stoch_k")) and pd.notna(last.get("stoch_d")):
        if last["stoch_k"] > last["stoch_d"] and last["stoch_k"] < 80:
            votes.append(("stochastic", 1, WEIGHTS["stochastic"]))
            details["Stochastic"] = f"صعود 📈 ({last['stoch_k']:.1f})"
        elif last["stoch_k"] < last["stoch_d"] and last["stoch_k"] > 20:
            votes.append(("stochastic", -1, WEIGHTS["stochastic"]))
            details["Stochastic"] = f"هبوط 📉 ({last['stoch_k']:.1f})"
        else:
            votes.append(("stochastic", 0, WEIGHTS["stochastic"]))
            details["Stochastic"] = f"محايد ⚪ ({last['stoch_k']:.1f})"

        if last["stoch_k"] > 80:
            warnings.append("Stochastic في تشبع شرائي (>80).")
        elif last["stoch_k"] < 20:
            warnings.append("Stochastic في تشبع بيعي (<20).")

    # 6) موقع السعر داخل نطاقات بولينجر
    if pd.notna(last.get("bb_upper")) and pd.notna(last.get("bb_lower")):
        if last["close"] >= last["bb_upper"]:
            votes.append(("bollinger", -1, WEIGHTS["bollinger"]))  # قرب الحزام العلوي = احتمال ارتداد هبوطي
            details["Bollinger Bands"] = "عند الحزام العلوي ⚠️"
        elif last["close"] <= last["bb_lower"]:
            votes.append(("bollinger", 1, WEIGHTS["bollinger"]))
            details["Bollinger Bands"] = "عند الحزام السفلي ⚠️"
        else:
            votes.append(("bollinger", 0, WEIGHTS["bollinger"]))
            details["Bollinger Bands"] = "داخل النطاق ⚪"

    # 7) ADX — قوة الاتجاه (لا يصوّت، لكنه يعدّل الثقة النهائية)
    adx_val = last["adx"]
    trend_strength_ok = adx_val > 25
    details["ADX (قوة الاتجاه)"] = (
        f"{'قوي 💪' if trend_strength_ok else 'ضعيف / تذبذب ⚠️'} ({adx_val:.1f})"
    )
    if not trend_strength_ok:
        warnings.append("قوة الاتجاه ضعيفة (ADX < 25) — السوق متذبذب، الإشارة أقل موثوقية.")

    # 8) عرض نطاق بولينجر — تحذير من سيولة/تقلب منخفض جدًا (سوق ضيق)
    bb_width = last.get("bb_width_pct", None)
    if pd.notna(bb_width) and bb_width < 0.4:
        warnings.append("انضغاط واضح في نطاقات بولينجر — تقلب منخفض جدًا، توخّ الحذر من كسر مفاجئ.")

    # ---- حساب النتيجة الموزونة ----
    weighted_score = sum(v * w for _, v, w in votes)
    normalized_confidence = round(abs(weighted_score) / MAX_SCORE * 100)

    # ---- تأكيد الفريم الزمني الأعلى ----
    higher_bias = _higher_timeframe_bias(df_higher) if df_higher is not None else 0
    primary_direction = 1 if weighted_score > 0 else (-1 if weighted_score < 0 else 0)

    mtf_note = None
    if higher_bias != 0 and primary_direction != 0:
        if higher_bias == primary_direction:
            normalized_confidence = min(100, normalized_confidence + 10)
            mtf_note = "✅ متوافق مع اتجاه الفريم الأعلى"
        else:
            normalized_confidence = max(0, normalized_confidence - 15)
            mtf_note = "⚠️ متعارض مع اتجاه الفريم الأعلى"
            warnings.append("اتجاه الفريم الأعلى مخالف لإشارة الفريم الحالي — الحذر مطلوب.")

    # ---- تخفيض الثقة إذا كان الاتجاه ضعيفًا (ADX) ----
    if not trend_strength_ok:
        normalized_confidence = round(normalized_confidence * 0.75)

    # ---- تحديد الاتجاه النهائي ----
    if weighted_score >= 1.5:
        direction = "صعود 📈 (شراء/CALL)"
    elif weighted_score <= -1.5:
        direction = "هبوط 📉 (بيع/PUT)"
    else:
        direction = "محايد ⚪ (لا إشارة واضحة)"

    # ---- تصنيف قوة الإشارة ----
    if normalized_confidence >= 80:
        strength_label = "قوية جدًا 🔥"
    elif normalized_confidence >= 60:
        strength_label = "قوية 💪"
    elif normalized_confidence >= 40:
        strength_label = "متوسطة ⚖️"
    else:
        strength_label = "ضعيفة ⚠️"

    # ---- الدعم والمقاومة ----
    support, resistance = support_resistance(data, lookback=60, window=3)

    return {
        "direction": direction,
        "confidence": normalized_confidence,
        "strength_label": strength_label,
        "adx_strength": adx_val,
        "details": details,
        "warnings": warnings,
        "mtf_note": mtf_note,
        "support": support,
        "resistance": resistance,
        "atr": last.get("atr"),
        "last_close": last["close"],
        "last_time": data.index[-1],
        "data": data,
    }
