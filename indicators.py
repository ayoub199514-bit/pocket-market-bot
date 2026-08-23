"""
indicators.py
حساب المؤشرات الفنية المستخدمة في تحليل اتجاه السوق:
- EMA (المتوسط المتحرك الأسي)
- RSI (مؤشر القوة النسبية)
- MACD (تقارب وتباعد المتوسطات المتحركة)
- ADX (مؤشر قوة الاتجاه)
- Bollinger Bands (نطاقات بولينجر — تقلب وضغط السعر)
- Stochastic Oscillator (مذبذب ستوكاستيك)
- ATR (متوسط المدى الحقيقي — قياس التقلب)
- Support/Resistance (أقرب مستويات دعم ومقاومة من القمم/القيعان الأخيرة)
"""

import pandas as pd
import numpy as np


def ema(series: pd.Series, period: int) -> pd.Series:
    """المتوسط المتحرك الأسي."""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """المتوسط المتحرك البسيط."""
    return series.rolling(window=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """مؤشر القوة النسبية (0-100)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """يعيد (خط MACD, خط الإشارة, الهيستوجرام)."""
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    مؤشر قوة الاتجاه (Average Directional Index).
    يتطلب أعمدة: high, low, close
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm[(plus_dm < 0) | (plus_dm < minus_dm)] = 0
    minus_dm[(minus_dm < 0) | (minus_dm < plus_dm)] = 0

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr_val = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_val)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_val)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return adx_val.fillna(0)


def bollinger_bands(series: pd.Series, period: int = 20, std_mult: float = 2.0):
    """يعيد (الحزام العلوي, الوسط, الحزام السفلي, نسبة عرض الحزام %)."""
    mid = sma(series, period)
    std = series.rolling(window=period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    bandwidth_pct = ((upper - lower) / mid.replace(0, np.nan)) * 100
    return upper, mid, lower, bandwidth_pct.fillna(0)


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    """مذبذب ستوكاستيك: يعيد (%K, %D)."""
    low_min = df["low"].rolling(window=k_period).min()
    high_max = df["high"].rolling(window=k_period).max()
    denom = (high_max - low_min).replace(0, np.nan)
    percent_k = 100 * (df["close"] - low_min) / denom
    percent_k = percent_k.fillna(50)
    percent_d = percent_k.rolling(window=d_period).mean().fillna(50)
    return percent_k, percent_d


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """متوسط المدى الحقيقي — قياس تقلب السوق (وحدة سعرية)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean().fillna(0)


def support_resistance(df: pd.DataFrame, lookback: int = 60, window: int = 3):
    """
    يحدد أقرب مستويي دعم ومقاومة بناءً على القمم/القيعان المحلية
    (swing highs/lows) ضمن آخر `lookback` شمعة.
    يعيد (دعم, مقاومة) كقيم سعرية، أو None إذا لم توجد بيانات كافية.
    """
    recent = df.tail(lookback)
    if len(recent) < window * 2 + 1:
        return None, None

    highs = recent["high"].values
    lows = recent["low"].values
    last_close = recent["close"].iloc[-1]

    swing_highs = []
    swing_lows = []
    for i in range(window, len(recent) - window):
        seg_high = highs[i - window: i + window + 1]
        seg_low = lows[i - window: i + window + 1]
        if highs[i] == seg_high.max():
            swing_highs.append(highs[i])
        if lows[i] == seg_low.min():
            swing_lows.append(lows[i])

    resistance_candidates = [h for h in swing_highs if h > last_close]
    support_candidates = [l for l in swing_lows if l < last_close]

    resistance = min(resistance_candidates) if resistance_candidates else recent["high"].max()
    support = max(support_candidates) if support_candidates else recent["low"].min()

    return support, resistance


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """يضيف كل المؤشرات كأعمدة جديدة إلى DataFrame يحتوي على open/high/low/close."""
    out = df.copy()
    out["ema_fast"] = ema(out["close"], 9)
    out["ema_slow"] = ema(out["close"], 21)
    out["ema_trend"] = ema(out["close"], 50)
    out["rsi"] = rsi(out["close"], 14)

    macd_line, signal_line, hist = macd(out["close"])
    out["macd"] = macd_line
    out["macd_signal"] = signal_line
    out["macd_hist"] = hist

    out["adx"] = adx(out, 14)

    bb_upper, bb_mid, bb_lower, bb_width = bollinger_bands(out["close"], 20, 2.0)
    out["bb_upper"] = bb_upper
    out["bb_mid"] = bb_mid
    out["bb_lower"] = bb_lower
    out["bb_width_pct"] = bb_width

    stoch_k, stoch_d = stochastic(out, 14, 3)
    out["stoch_k"] = stoch_k
    out["stoch_d"] = stoch_d

    out["atr"] = atr(out, 14)

    return out
