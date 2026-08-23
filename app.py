"""
app.py
تطبيق ويب (Streamlit) لتحليل اتجاه السوق — مساعد قرار وليس أداة تداول آلي.
نسخة متطورة: مؤشرات إضافية + تصويت موزون + تأكيد فريم زمني أعلى +
دعم/مقاومة + تحذيرات ذكية + وضع تحليل تلقائي.

⚠️ تنبيه:
- لا يتصل هذا التطبيق بحساب Pocket Option ولا ينفذ صفقات.
- البيانات من مصدر خارجي (Yahoo Finance) وقد تختلف قليلًا عن أسعار المنصة.
- هذه إشارات احتمالية بناءً على مؤشرات فنية تاريخية، وليست توصية مالية
  ولا ضمانًا لنتيجة أي صفقة. تداول الخيارات الثنائية ينطوي على مخاطر عالية
  وقد تخسر رأس مالك بالكامل.
"""

import time
from datetime import datetime

import streamlit as st
import plotly.graph_objects as go

from data_fetch import (
    fetch_ohlc,
    fetch_higher_timeframe_ohlc,
    SYMBOL_MAP,
    TIMEFRAME_MAP,
    CANDLE_CHECK_INTERVAL_SECONDS,
)
from signal_engine import generate_signal

st.set_page_config(page_title="محلل اتجاه السوق المتطور", page_icon="📊", layout="wide")

st.title("📊 محلل اتجاه السوق — نسخة متطورة")
st.caption(
    "مؤشرات: EMA · RSI · MACD · ADX · Bollinger Bands · Stochastic · ATR "
    "+ تأكيد من فريم زمني أعلى + مستويات دعم/مقاومة. "
    "لا يتصل بحسابك على أي منصة ولا ينفذ صفقات تلقائيًا."
)

# ---------------------------------------------------------------------------
# الحالة الدائمة عبر إعادة تشغيل Streamlit (session_state)
# ---------------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
if "last_run_meta" not in st.session_state:
    st.session_state.last_run_meta = None
if "update_mode" not in st.session_state:
    st.session_state.update_mode = "متوقف"
if "history" not in st.session_state:
    st.session_state.history = []  # سجل آخر الإشارات لهذه الجلسة
if "last_candle_seen" not in st.session_state:
    st.session_state.last_candle_seen = {}  # آخر وقت شمعة رُصد لكل (أصل, فريم)


def _record_result(result: dict, symbol_label: str, timeframe_label: str, higher_label) -> None:
    st.session_state.result = result
    st.session_state.last_run_meta = {
        "symbol": symbol_label,
        "timeframe": timeframe_label,
        "higher_timeframe": higher_label,
        "run_at": datetime.now().strftime("%H:%M:%S"),
    }
    st.session_state.history.insert(0, {
        "الوقت": datetime.now().strftime("%H:%M:%S"),
        "الأصل": symbol_label,
        "الفريم": timeframe_label,
        "الاتجاه": result["direction"],
        "الثقة": f"{result['confidence']}%",
        "القوة": result["strength_label"],
    })
    st.session_state.history = st.session_state.history[:20]


def run_analysis(symbol_label: str, timeframe_label: str, use_mtf: bool) -> None:
    """يجلب بيانات جديدة ويشغّل التحليل الكامل من الصفر (يُستخدم مع الزر اليدوي والوضع الزمني الثابت)."""
    df = fetch_ohlc(symbol_label, timeframe_label)
    df_higher, higher_label = (None, None)
    if use_mtf:
        df_higher, higher_label = fetch_higher_timeframe_ohlc(symbol_label, timeframe_label)
    result = generate_signal(df, df_higher)
    _record_result(result, symbol_label, timeframe_label, higher_label)

    key = f"{symbol_label}|{timeframe_label}"
    st.session_state.last_candle_seen[key] = df.index[-1]


def check_and_analyze_on_new_candle(symbol_label: str, timeframe_label: str, use_mtf: bool) -> bool:
    """
    يجلب آخر البيانات ويقارن وقت آخر شمعة بما تم رصده سابقًا.
    يُجري تحليلًا كاملًا فقط إذا ظهرت شمعة جديدة فعليًا (إغلاق شمعة).
    يعيد True إذا تم تحليل جديد، و False إذا لم تتغيّر الشمعة بعد.
    """
    df = fetch_ohlc(symbol_label, timeframe_label)
    key = f"{symbol_label}|{timeframe_label}"
    last_candle_time = df.index[-1]
    prev_candle_time = st.session_state.last_candle_seen.get(key)

    is_new_candle = prev_candle_time is None or last_candle_time != prev_candle_time
    if not is_new_candle:
        return False

    df_higher, higher_label = (None, None)
    if use_mtf:
        df_higher, higher_label = fetch_higher_timeframe_ohlc(symbol_label, timeframe_label)
    result = generate_signal(df, df_higher)
    _record_result(result, symbol_label, timeframe_label, higher_label)
    st.session_state.last_candle_seen[key] = last_candle_time
    return True


with st.sidebar:
    st.header("⚙️ الإعدادات")
    symbol_label = st.selectbox("اختر الأصل", list(SYMBOL_MAP.keys()))
    timeframe_label = st.selectbox("الفريم الزمني", list(TIMEFRAME_MAP.keys()), index=2)
    use_mtf = st.checkbox("تأكيد من الفريم الزمني الأعلى (موصى به)", value=True)

    run_button = st.button("🔍 تحليل الآن", use_container_width=True, type="primary")

    st.divider()
    st.subheader("🤖 التحديث التلقائي")
    update_mode = st.radio(
        "طريقة التحديث",
        ["متوقف", "🕯️ تحليل عند إغلاق كل شمعة", "⏱️ كل فترة زمنية ثابتة"],
        index=["متوقف", "🕯️ تحليل عند إغلاق كل شمعة", "⏱️ كل فترة زمنية ثابتة"].index(
            st.session_state.update_mode
        ) if st.session_state.update_mode in
        ["متوقف", "🕯️ تحليل عند إغلاق كل شمعة", "⏱️ كل فترة زمنية ثابتة"] else 0,
        help=(
            "🕯️ عند إغلاق كل شمعة: يراقب البوت السوق ويحلل تلقائيًا فقط عندما "
            "تُغلق شمعة جديدة فعليًا في الفريم المختار — الأنسب للتداول الحقيقي.\n\n"
            "⏱️ فترة ثابتة: يعيد التحليل كل عدد ثوانٍ تحدده، بغض النظر عن إغلاق الشمعة."
        ),
    )
    st.session_state.update_mode = update_mode

    refresh_seconds = 30
    if update_mode == "⏱️ كل فترة زمنية ثابتة":
        refresh_seconds = st.slider("التحديث كل (ثانية)", min_value=10, max_value=300, value=30, step=5)
    elif update_mode == "🕯️ تحليل عند إغلاق كل شمعة":
        poll_seconds = CANDLE_CHECK_INTERVAL_SECONDS.get(timeframe_label, 15)
        st.caption(f"🔎 يفحص البوت كل {poll_seconds} ثانية هل أُغلقت شمعة جديدة على فريم «{timeframe_label}».")

    st.divider()
    st.warning(
        "⚠️ هذا التطبيق أداة تحليل فقط وليس توصية مالية. تداول الخيارات "
        "الثنائية والعقود مقابل الفروقات ينطوي على مخاطر عالية جدًا، وقد "
        "تخسر رأس مالك بالكامل. قرار الدخول أو الخروج من أي صفقة يبقى "
        "مسؤوليتك الكاملة."
    )

# ---- تشغيل التحليل ----
triggered_manually = run_button
error_msg = None
new_candle_detected = False

if triggered_manually:
    try:
        with st.spinner("جاري جلب البيانات وتحليلها..."):
            run_analysis(symbol_label, timeframe_label, use_mtf)
    except Exception as e:
        error_msg = str(e)

elif st.session_state.update_mode == "⏱️ كل فترة زمنية ثابتة":
    try:
        with st.spinner("تحليل تلقائي جارٍ..."):
            run_analysis(symbol_label, timeframe_label, use_mtf)
    except Exception as e:
        error_msg = str(e)

elif st.session_state.update_mode == "🕯️ تحليل عند إغلاق كل شمعة":
    try:
        with st.spinner("جاري فحص آخر شمعة..."):
            new_candle_detected = check_and_analyze_on_new_candle(
                symbol_label, timeframe_label, use_mtf
            )
    except Exception as e:
        error_msg = str(e)

# ---- عرض النتيجة ----
if error_msg:
    st.error(f"حدث خطأ: {error_msg}")
elif st.session_state.result is not None:
    result = st.session_state.result
    meta = st.session_state.last_run_meta

    mtf_line = ""
    if meta.get("higher_timeframe"):
        mtf_line = f" | تأكيد من فريم: {meta['higher_timeframe']}"
    mode_flag = ""
    if st.session_state.update_mode == "🕯️ تحليل عند إغلاق كل شمعة":
        mode_flag = " | 🕯️ مراقبة إغلاق الشموع نشطة"
    elif st.session_state.update_mode == "⏱️ كل فترة زمنية ثابتة":
        mode_flag = " | ⏱️ تحديث تلقائي ثابت نشط"

    st.caption(
        f"آخر تحليل: {meta['symbol']} | {meta['timeframe']} | "
        f"وقت التنفيذ: {meta['run_at']}{mtf_line}{mode_flag}"
    )
    if st.session_state.update_mode == "🕯️ تحليل عند إغلاق كل شمعة" and not new_candle_detected and not triggered_manually:
        st.caption("⏳ لا توجد شمعة جديدة بعد — النتيجة أعلاه لا تزال آخر شمعة مُغلقة.")

    # ---- صف النتيجة الرئيسية ----
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("الاتجاه", result["direction"])
    col2.metric("نسبة الثقة", f"{result['confidence']}%")
    col3.metric("قوة الإشارة", result["strength_label"])
    col4.metric("آخر سعر إغلاق", f"{result['last_close']:.5f}")

    if result.get("mtf_note"):
        st.info(result["mtf_note"])

    # ---- التحذيرات الذكية ----
    if result.get("warnings"):
        with st.container():
            for w in result["warnings"]:
                st.warning(w)

    # ---- الدعم والمقاومة ----
    sup_col, res_col, atr_col = st.columns(3)
    if result.get("support") is not None:
        sup_col.metric("🟢 أقرب دعم", f"{result['support']:.5f}")
    if result.get("resistance") is not None:
        res_col.metric("🔴 أقرب مقاومة", f"{result['resistance']:.5f}")
    if result.get("atr") is not None:
        atr_col.metric("📏 التقلب (ATR)", f"{result['atr']:.5f}")

    st.caption(f"آخر تحديث للبيانات: {result['last_time']}")

    # ---- تفاصيل كل مؤشر ----
    st.subheader("تفاصيل المؤشرات")
    detail_items = list(result["details"].items())
    n_cols = min(4, len(detail_items))
    detail_cols = st.columns(n_cols)
    for i, (name, value) in enumerate(detail_items):
        detail_cols[i % n_cols].metric(name, value)

    # ---- الرسم البياني الرئيسي (شموع + EMA + Bollinger + دعم/مقاومة) ----
    st.subheader("الرسم البياني (شموع + مؤشرات)")
    data = result["data"].tail(150)

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=data.index, open=data["open"], high=data["high"],
            low=data["low"], close=data["close"], name="السعر",
        )
    )
    fig.add_trace(go.Scatter(x=data.index, y=data["ema_fast"], name="EMA 9", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=data.index, y=data["ema_slow"], name="EMA 21", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=data.index, y=data["ema_trend"], name="EMA 50", line=dict(width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=data.index, y=data["bb_upper"], name="Bollinger عليا",
                              line=dict(width=1, color="gray", dash="dash")))
    fig.add_trace(go.Scatter(x=data.index, y=data["bb_lower"], name="Bollinger سفلى",
                              line=dict(width=1, color="gray", dash="dash")))

    if result.get("support") is not None:
        fig.add_hline(y=result["support"], line_dash="dot", line_color="green",
                       annotation_text="دعم")
    if result.get("resistance") is not None:
        fig.add_hline(y=result["resistance"], line_dash="dot", line_color="red",
                       annotation_text="مقاومة")

    fig.update_layout(height=520, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # ---- RSI / MACD / Stochastic ----
    col_rsi, col_macd, col_stoch = st.columns(3)

    with col_rsi:
        st.subheader("RSI")
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=data.index, y=data["rsi"], name="RSI"))
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
        fig_rsi.update_layout(height=280)
        st.plotly_chart(fig_rsi, use_container_width=True)

    with col_macd:
        st.subheader("MACD")
        fig_macd = go.Figure()
        fig_macd.add_trace(go.Scatter(x=data.index, y=data["macd"], name="MACD"))
        fig_macd.add_trace(go.Scatter(x=data.index, y=data["macd_signal"], name="Signal"))
        fig_macd.add_trace(go.Bar(x=data.index, y=data["macd_hist"], name="Histogram"))
        fig_macd.update_layout(height=280)
        st.plotly_chart(fig_macd, use_container_width=True)

    with col_stoch:
        st.subheader("Stochastic")
        fig_stoch = go.Figure()
        fig_stoch.add_trace(go.Scatter(x=data.index, y=data["stoch_k"], name="%K"))
        fig_stoch.add_trace(go.Scatter(x=data.index, y=data["stoch_d"], name="%D"))
        fig_stoch.add_hline(y=80, line_dash="dash", line_color="red")
        fig_stoch.add_hline(y=20, line_dash="dash", line_color="green")
        fig_stoch.update_layout(height=280)
        st.plotly_chart(fig_stoch, use_container_width=True)

    # ---- سجل آخر الإشارات ----
    if st.session_state.history:
        st.subheader("🕓 سجل آخر الإشارات (هذه الجلسة)")
        st.dataframe(st.session_state.history, use_container_width=True, hide_index=True)

else:
    st.info("اختر الأصل والفريم الزمني من القائمة الجانبية، ثم اضغط 'تحليل الآن'.")

# ---- حلقة التحديث التلقائي ----
if st.session_state.update_mode == "⏱️ كل فترة زمنية ثابتة":
    countdown_placeholder = st.empty()
    for remaining in range(refresh_seconds, 0, -1):
        countdown_placeholder.caption(f"⏳ التحليل التالي خلال {remaining} ثانية...")
        time.sleep(1)
    st.rerun()

elif st.session_state.update_mode == "🕯️ تحليل عند إغلاق كل شمعة":
    poll_seconds = CANDLE_CHECK_INTERVAL_SECONDS.get(timeframe_label, 15)
    countdown_placeholder = st.empty()
    for remaining in range(poll_seconds, 0, -1):
        countdown_placeholder.caption(f"👁️ يراقب إغلاق الشمعة القادمة — الفحص التالي خلال {remaining} ثانية...")
        time.sleep(1)
    st.rerun()
