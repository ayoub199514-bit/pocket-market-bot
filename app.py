"""
app.py
تطبيق ويب (Streamlit) لتحليل اتجاه السوق — مساعد قرار وليس أداة تداول آلي.

⚠️ تنبيه:
- لا يتصل هذا التطبيق بحساب Pocket Option ولا ينفذ صفقات.
- البيانات من مصدر خارجي (Yahoo Finance) وقد تختلف قليلًا عن أسعار المنصة.
- هذه إشارات احتمالية بناءً على مؤشرات فنية، وليست توصية مالية.
"""

import streamlit as st
import plotly.graph_objects as go

from data_fetch import fetch_ohlc, SYMBOL_MAP, TIMEFRAME_MAP
from signal_engine import generate_signal

st.set_page_config(page_title="محلل اتجاه السوق", page_icon="📊", layout="wide")

st.title("📊 محلل اتجاه السوق")
st.caption(
    "مساعد قرار مبني على مؤشرات فنية (EMA, RSI, MACD, ADX) — "
    "لا يتصل بحسابك على أي منصة ولا ينفذ صفقات تلقائيًا."
)

with st.sidebar:
    st.header("⚙️ الإعدادات")
    symbol_label = st.selectbox("اختر الأصل", list(SYMBOL_MAP.keys()))
    timeframe_label = st.selectbox("الفريم الزمني", list(TIMEFRAME_MAP.keys()), index=2)
    run_button = st.button("🔍 تحليل الآن", use_container_width=True)

    st.divider()
    st.warning(
        "هذا التطبيق أداة تحليل فقط. قرار الدخول أو الخروج من أي صفقة "
        "يبقى مسؤوليتك الكاملة."
    )

if run_button:
    try:
        with st.spinner("جاري جلب البيانات وتحليلها..."):
            df = fetch_ohlc(symbol_label, timeframe_label)
            result = generate_signal(df)

        # ---- صف النتيجة الرئيسية ----
        col1, col2, col3 = st.columns(3)
        col1.metric("الاتجاه", result["direction"])
        col2.metric("نسبة الثقة", f"{result['confidence']}%")
        col3.metric("آخر سعر إغلاق", f"{result['last_close']:.5f}")

        st.caption(f"آخر تحديث للبيانات: {result['last_time']}")

        # ---- تفاصيل كل مؤشر ----
        st.subheader("تفاصيل المؤشرات")
        detail_cols = st.columns(len(result["details"]))
        for col, (name, value) in zip(detail_cols, result["details"].items()):
            col.metric(name, value)

        # ---- الرسم البياني ----
        st.subheader("الرسم البياني (شموع + المتوسطات المتحركة)")
        data = result["data"].tail(150)

        fig = go.Figure()
        fig.add_trace(
            go.Candlestick(
                x=data.index,
                open=data["open"],
                high=data["high"],
                low=data["low"],
                close=data["close"],
                name="السعر",
            )
        )
        fig.add_trace(
            go.Scatter(x=data.index, y=data["ema_fast"], name="EMA 9", line=dict(width=1.5))
        )
        fig.add_trace(
            go.Scatter(x=data.index, y=data["ema_slow"], name="EMA 21", line=dict(width=1.5))
        )
        fig.update_layout(height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # ---- RSI و MACD في أسفل ----
        col_rsi, col_macd = st.columns(2)

        with col_rsi:
            st.subheader("RSI")
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(x=data.index, y=data["rsi"], name="RSI"))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
            fig_rsi.update_layout(height=300)
            st.plotly_chart(fig_rsi, use_container_width=True)

        with col_macd:
            st.subheader("MACD")
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Scatter(x=data.index, y=data["macd"], name="MACD"))
            fig_macd.add_trace(go.Scatter(x=data.index, y=data["macd_signal"], name="Signal"))
            fig_macd.add_trace(go.Bar(x=data.index, y=data["macd_hist"], name="Histogram"))
            fig_macd.update_layout(height=300)
            st.plotly_chart(fig_macd, use_container_width=True)

    except Exception as e:
        st.error(f"حدث خطأ: {e}")
else:
    st.info("اختر الأصل والفريم الزمني من القائمة الجانبية، ثم اضغط 'تحليل الآن'.")
