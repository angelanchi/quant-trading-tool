# -*- coding: utf-8 -*-
"""
Risk Analysis Page

Features:
- VaR calculation (Historical, Parametric, Monte Carlo)
- CVaR (Expected Shortfall)
- Risk metrics dashboard
- Drawdown analysis
- Portfolio risk decomposition
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


from views._shared import (chart, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# Initialize session state
if 'risk_metrics' not in st.session_state:
    st.session_state.risk_metrics = None
if 'price_data' not in st.session_state:
    st.session_state.price_data = {}


def get_data_manager():
    """Get or create DataManager instance."""
    if 'data_manager' not in st.session_state:
        try:
            from core import DataManager
            st.session_state.data_manager = DataManager()
        except Exception as e:
            st.error(f"Failed to initialize DataManager: {e}")
            return None
    return st.session_state.data_manager


def get_risk_calculator():
    """Get RiskCalculator instance."""
    try:
        from core import RiskCalculator
        return RiskCalculator()
    except Exception as e:
        st.error(f"Failed to initialize RiskCalculator: {e}")
        return None


def plot_drawdown(returns: pd.Series):
    """Plot drawdown chart."""
    # Calculate cumulative returns and drawdown
    cum_returns = (1 + returns).cumprod()
    peak = cum_returns.cummax()
    drawdown = (cum_returns - peak) / peak * 100

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=drawdown.index,
        y=drawdown.values,
        fill='tozeroy',
        mode='lines',
        name='Drawdown',
        line=dict(color=RED, width=1),
        fillcolor='rgba(255, 0, 0, 0.3)'
    ))

    fig.update_layout(
        title='Drawdown Over Time',
        xaxis_title='Date',
        yaxis_title='Drawdown (%)',
        height=400
    )

    return fig


def plot_returns_distribution(returns: pd.Series):
    """Plot returns distribution with VaR/CVaR markers."""
    fig = go.Figure()

    # Histogram
    fig.add_trace(go.Histogram(
        x=returns.values * 100,
        nbinsx=50,
        name='Returns',
        marker_color=ACCENT,
        opacity=0.7
    ))

    # Calculate VaR and CVaR for markers
    var_95 = np.percentile(returns, 5) * 100
    cvar_95 = returns[returns <= np.percentile(returns, 5)].mean() * 100

    # Add VaR line
    fig.add_vline(
        x=var_95,
        line_dash="dash",
        line_color=ACCENT2,
        annotation_text=f"VaR 95%: {var_95:.2f}%"
    )

    # Add CVaR line
    fig.add_vline(
        x=cvar_95,
        line_dash="dash",
        line_color=RED,
        annotation_text=f"CVaR 95%: {cvar_95:.2f}%"
    )

    fig.update_layout(
        title='Returns Distribution with VaR/CVaR',
        xaxis_title='Daily Return (%)',
        yaxis_title='Frequency',
        height=400
    )

    return fig


def plot_rolling_volatility(returns: pd.Series, window: int = 21):
    """Plot rolling volatility."""
    rolling_vol = returns.rolling(window=window).std() * np.sqrt(252) * 100

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=rolling_vol.index,
        y=rolling_vol.values,
        mode='lines',
        name=f'{window}-day Rolling Volatility',
        line=dict(color=ACCENT, width=2)
    ))

    # Add mean line
    mean_vol = rolling_vol.mean()
    fig.add_hline(
        y=mean_vol,
        line_dash="dash",
        line_color=GRAY,
        annotation_text=f"Mean: {mean_vol:.1f}%"
    )

    fig.update_layout(
        title=f'Rolling {window}-Day Annualized Volatility',
        xaxis_title='Date',
        yaxis_title='Volatility (%)',
        height=400
    )

    return fig


def plot_var_comparison(returns: pd.Series, confidence: float = 0.95):
    """Plot VaR comparison across methods."""
    calc = get_risk_calculator()
    if not calc:
        return None

    methods = ['Historical', 'Parametric', 'Monte Carlo']
    var_values = []

    # Historical VaR
    var_hist = calc.var_historical(returns, confidence)
    var_values.append(abs(var_hist) * 100)

    # Parametric VaR
    var_param = calc.var_parametric(returns, confidence)
    var_values.append(abs(var_param) * 100)

    # Monte Carlo VaR
    var_mc = calc.var_monte_carlo(returns, confidence)
    var_values.append(abs(var_mc) * 100)

    fig = go.Figure(data=[go.Bar(
        x=methods,
        y=var_values,
        marker_color=[ACCENT, ACCENT2, GRAY]
    )])

    fig.update_layout(
        title=f'VaR Comparison ({int(confidence*100)}% Confidence)',
        xaxis_title='Method',
        yaxis_title='VaR (%)',
        height=400
    )

    return fig


def plot_correlation_heatmap(returns: pd.DataFrame):
    """Plot correlation heatmap."""
    corr = returns.corr()

    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.index,
        colorscale='RdBu',
        zmid=0,
        text=np.round(corr.values, 2),
        texttemplate='%{text}',
        textfont={"size": 10}
    ))

    fig.update_layout(
        title='Correlation Matrix',
        height=400
    )

    return fig


page_header("風險分析（舊版）", "單一資料來源的風險指標；含 VaR 回測的完整版本見 ④ 風險與部位。")

# Data source selection
st.subheader("選擇資料來源")

data_source = st.radio(
    "分析風險",
    ["自訂股票", "回測結果（如可用）"],
    key="data_source"
)

symbols_input = ""
if data_source == "自訂股票":
    symbols_input = st.text_input(
        "輸入股票代碼（以逗號分隔）",
        placeholder="例如：AAPL, MSFT, GOOGL",
        key="risk_symbols"
    )

# Date range
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "開始日期",
        value=datetime.now() - timedelta(days=365*2),
        key="risk_start"
    )
with col2:
    end_date = st.date_input(
        "結束日期",
        value=datetime.now(),
        key="risk_end"
    )

# Risk parameters
st.subheader("風險參數")
col1, col2, col3 = st.columns(3)

with col1:
    confidence = st.selectbox(
        "信賴水準 (Confidence Level)",
        [0.90, 0.95, 0.99],
        index=1,
        format_func=lambda x: f"{x*100:.0f}%",
        key="confidence"
    )

with col2:
    var_method = st.selectbox(
        "主要 VaR 方法",
        ["歷史模擬法 (Historical)", "參數法 (Parametric)", "蒙地卡羅模擬 (Monte Carlo)"],
        key="var_method"
    )

with col3:
    holding_period = st.selectbox(
        "持有期間",
        [1, 5, 10, 21],
        format_func=lambda x: f"{x} 天",
        key="holding_period"
    )

# Portfolio weights (optional)
st.subheader("投資組合權重（選擇性）")
use_equal_weights = st.checkbox("使用等權重", value=True, key="equal_weights")

if not use_equal_weights and symbols_input:
    symbols = [s.strip().upper() for s in symbols_input.split(',')]
    weights = {}
    cols = st.columns(len(symbols))
    for i, symbol in enumerate(symbols):
        with cols[i]:
            weights[symbol] = st.number_input(
                f"{symbol} weight",
                min_value=0.0,
                max_value=1.0,
                value=1.0/len(symbols),
                step=0.05,
                key=f"weight_{symbol}"
            )

# Calculate risk
st.markdown("---")

if st.button("計算風險指標", type="primary"):
    if not symbols_input and data_source == "自訂股票":
        st.warning("請輸入至少一個股票代碼")
    else:
        symbols = [s.strip().upper() for s in symbols_input.split(',')] if symbols_input else []

        dm = get_data_manager()
        calc = get_risk_calculator()

        if dm and calc:
            with st.spinner("正在取得價格資料..."):
                # Fetch data
                price_data = {}
                for symbol in symbols:
                    try:
                        df = dm.fetch_ohlcv(
                            symbol,
                            start_date.strftime('%Y-%m-%d'),
                            end_date.strftime('%Y-%m-%d')
                        )
                        if df is not None and not df.empty:
                            price_data[symbol] = df['close']
                    except Exception as e:
                        st.error(f"無法取得 {symbol} 的資料：{e}")

                if not price_data:
                    st.error("無可用的價格資料")
                else:
                    # Combine into DataFrame
                    prices_df = pd.DataFrame(price_data)
                    prices_df = prices_df.dropna()

                    if prices_df.empty:
                        st.error("選定股票無重疊資料")
                    else:
                        st.success(f"已載入 {len(price_data)} 個股票共 {len(prices_df)} 天的資料")

                        # Calculate returns
                        returns = prices_df.pct_change().dropna()

                        # Calculate portfolio returns if multiple symbols
                        if len(symbols) > 1:
                            if use_equal_weights:
                                weights_dict = {s: 1/len(symbols) for s in symbols}
                            else:
                                weights_dict = weights
                                # Normalize weights
                                total_weight = sum(weights_dict.values())
                                weights_dict = {k: v/total_weight for k, v in weights_dict.items()}

                            portfolio_returns = sum(returns[s] * weights_dict[s] for s in symbols)
                        else:
                            portfolio_returns = returns.iloc[:, 0]

                        with st.spinner("計算風險指標中..."):
                            try:
                                # Calculate comprehensive risk metrics
                                metrics = calc.calculate_all_metrics(
                                    portfolio_returns,
                                    confidence=confidence,
                                    risk_free_rate=0.02,
                                    periods_per_year=252
                                )

                                st.session_state.risk_metrics = metrics
                                st.session_state.risk_returns = returns
                                st.session_state.portfolio_returns = portfolio_returns
                                st.success("風險分析已完成！")

                            except Exception as e:
                                st.error(f"風險計算失敗：{e}")
                                import traceback
                                st.error(traceback.format_exc())

# Results section
st.markdown("---")
st.subheader("風險指標")

if st.session_state.risk_metrics is not None:
    metrics = st.session_state.risk_metrics
    portfolio_returns = st.session_state.portfolio_returns
    returns = st.session_state.risk_returns

    # Key risk metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            f"風險值 ({int(confidence*100)}%)",
            f"{metrics.var_historical:.2%}",
            help="風險值 (VaR) - 給定信賴水準下的最大預期損失"
        )

    with col2:
        st.metric(
            f"條件風險值 ({int(confidence*100)}%)",
            f"{metrics.cvar:.2%}",
            help="條件風險值 (CVaR) - 超過風險值時的平均損失"
        )

    with col3:
        st.metric(
            "夏普比率",
            f"{metrics.sharpe_ratio:.2f}",
            help="風險調整報酬度量"
        )

    with col4:
        st.metric(
            "最大回撤",
            f"{metrics.max_drawdown:.2%}",
            help="從高峰到低谷的最大跌幅"
        )

    # Secondary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Sortino 比率",
            f"{metrics.sortino_ratio:.2f}",
            help="下行風險調整報酬"
        )

    with col2:
        st.metric(
            "Calmar 比率",
            f"{metrics.calmar_ratio:.2f}",
            help="相對於最大回撤的報酬"
        )

    with col3:
        st.metric(
            "年波動率",
            f"{metrics.volatility:.2%}",
            help="年化報酬標準差"
        )

    with col4:
        st.metric(
            "年報酬率",
            f"{metrics.annual_return:.2%}",
            help="年化報酬率"
        )

    # Distribution metrics
    st.markdown("---")
    st.subheader("分布分析")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "偏度",
            f"{metrics.skewness:.3f}",
            help="報酬分布不對稱的度量"
        )

    with col2:
        st.metric(
            "峰度",
            f"{metrics.kurtosis:.3f}",
            help="尾部厚度的度量（超額峰度）"
        )

    with col3:
        # Jarque-Bera test for normality
        from scipy import stats
        jb_stat, jb_pvalue = stats.jarque_bera(portfolio_returns)
        is_normal = "是" if jb_pvalue > 0.05 else "否"
        st.metric(
            "符合常態分布？",
            is_normal,
            help=f"Jarque-Bera p 值：{jb_pvalue:.4f}"
        )

    # VaR comparison
    st.markdown("---")
    st.subheader("VaR 方法比較")

    fig = plot_var_comparison(portfolio_returns, confidence)
    if fig:
        chart(fig)

    # Charts
    st.markdown("---")
    st.subheader("風險視覺化")

    col1, col2 = st.columns(2)

    with col1:
        # Drawdown chart
        fig = plot_drawdown(portfolio_returns)
        chart(fig)

    with col2:
        # Returns distribution
        fig = plot_returns_distribution(portfolio_returns)
        chart(fig)

    # Rolling volatility
    col1, col2 = st.columns(2)

    with col1:
        fig = plot_rolling_volatility(portfolio_returns, window=21)
        chart(fig)

    with col2:
        # Correlation matrix (if multiple assets)
        if len(returns.columns) > 1:
            fig = plot_correlation_heatmap(returns)
            chart(fig)
        else:
            st.info("相關係數矩陣需要多個資產")

    # Detailed metrics table
    st.markdown("---")
    st.subheader("詳細指標")

    metrics_data = {
        '指標': [
            '風險值（歷史模擬法）',
            '風險值（參數法）',
            '風險值（蒙地卡羅模擬）',
            '條件風險值 / 預期缺口',
            '年報酬率',
            '年波動率',
            '夏普比率',
            'Sortino 比率',
            'Calmar 比率',
            '最大回撤',
            '平均回撤',
            '偏度',
            '峰度'
        ],
        '值': [
            f"{metrics.var_historical:.4%}",
            f"{metrics.var_parametric:.4%}",
            f"{metrics.var_monte_carlo:.4%}",
            f"{metrics.cvar:.4%}",
            f"{metrics.annual_return:.4%}",
            f"{metrics.volatility:.4%}",
            f"{metrics.sharpe_ratio:.4f}",
            f"{metrics.sortino_ratio:.4f}",
            f"{metrics.calmar_ratio:.4f}",
            f"{metrics.max_drawdown:.4%}",
            f"{metrics.avg_drawdown:.4%}",
            f"{metrics.skewness:.4f}",
            f"{metrics.kurtosis:.4f}"
        ]
    }

    metrics_df = pd.DataFrame(metrics_data)
    st.dataframe(metrics_df, width="stretch", hide_index=True)

    # Export
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        csv = metrics_df.to_csv(index=False)
        st.download_button(
            "下載風險報告",
            data=csv,
            file_name="risk_metrics.csv",
            mime="text/csv"
        )

    with col2:
        returns_csv = portfolio_returns.to_csv()
        st.download_button(
            "下載報酬資料",
            data=returns_csv,
            file_name="returns.csv",
            mime="text/csv"
        )

else:
    # Placeholder metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("風險值 (95%)", "-", help="風險值 (VaR)")
    with col2:
        st.metric("條件風險值 (95%)", "-", help="預期缺口")
    with col3:
        st.metric("夏普比率", "-")
    with col4:
        st.metric("最大回撤", "-")

    st.info("計算風險指標以查看分析結果。")

# Help section
with st.expander("風險指標詞彙表"):
    st.markdown("""
    **風險值 (VaR)**
    - 給定信賴水準下的最大預期損失
    - VaR(95%) = -2% 表示 95% 的時間內，日損失不會超過 2%

    **條件風險值 (CVaR) / 預期缺口**
    - 超過風險值時的平均損失
    - 比 VaR 更保守，因為它考慮了尾部風險

    **夏普比率**
    - 風險調整報酬：(報酬 - 無風險利率) / 波動率
    - 更高越好；>1 良好，>2 優秀

    **Sortino 比率**
    - 類似夏普比率，但僅懲罰下行波動
    - 適用於不對稱的報酬分布

    **Calmar 比率**
    - 年報酬率除以最大回撤
    - 測量相對於最壞情況的報酬

    **最大回撤**
    - 投資組合價值從高峰到低谷的最大跌幅
    - 了解最壞情況損失的關鍵指標

    **偏度**
    - 測量報酬分布的不對稱性
    - 負偏度 = 極端損失多於獲利

    **峰度**
    - 測量報酬分布中的「厚尾」
    - 更高的峰度 = 比常態分布更多的極端事件
    """)
