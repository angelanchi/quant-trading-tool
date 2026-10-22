# -*- coding: utf-8 -*-
"""
Portfolio Optimization Page

Features:
- Asset selection
- Optimization method selection (Max Sharpe, Min Vol, HRP, Black-Litterman)
- Efficient frontier visualization
- Weight allocation and discrete allocation
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


from views._shared import (chart, money, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# Initialize session state
if 'optimization_result' not in st.session_state:
    st.session_state.optimization_result = None
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


def get_portfolio_optimizer():
    """Get PortfolioOptimizer instance."""
    try:
        from core import PortfolioOptimizer
        return PortfolioOptimizer()
    except Exception as e:
        st.error(f"Failed to initialize PortfolioOptimizer: {e}")
        return None


def plot_weights_pie(weights: dict, title: str = "Portfolio Weights"):
    """Create pie chart for portfolio weights."""
    # Filter out zero weights
    filtered_weights = {k: v for k, v in weights.items() if v > 0.001}

    fig = go.Figure(data=[go.Pie(
        labels=list(filtered_weights.keys()),
        values=list(filtered_weights.values()),
        textinfo='label+percent',
        hole=0.3
    )])

    fig.update_layout(
        title=title,
        height=400
    )

    return fig


def plot_efficient_frontier(ef_data: pd.DataFrame, optimal_point: tuple = None):
    """Plot efficient frontier with optional optimal point."""
    fig = go.Figure()

    # Efficient frontier line
    fig.add_trace(go.Scatter(
        x=ef_data['volatility'] * 100,
        y=ef_data['return'] * 100,
        mode='lines',
        name='Efficient Frontier',
        line=dict(color=ACCENT, width=2)
    ))

    # Optimal point
    if optimal_point:
        vol, ret = optimal_point
        fig.add_trace(go.Scatter(
            x=[vol * 100],
            y=[ret * 100],
            mode='markers',
            name='Optimal Portfolio',
            marker=dict(color=RED, size=15, symbol='star')
        ))

    fig.update_layout(
        title='Efficient Frontier',
        xaxis_title='Volatility (%)',
        yaxis_title='Expected Return (%)',
        height=500,
        showlegend=True
    )

    return fig


def plot_weights_bar(weights: dict):
    """Create bar chart for portfolio weights."""
    fig = go.Figure(data=[go.Bar(
        x=list(weights.keys()),
        y=[v * 100 for v in weights.values()],
        marker_color=ACCENT
    )])

    fig.update_layout(
        title='Portfolio Weights',
        xaxis_title='Asset',
        yaxis_title='Weight (%)',
        height=400
    )

    return fig


def plot_correlation_heatmap(returns: pd.DataFrame):
    """Create correlation heatmap."""
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


page_header("投資組合最佳化", "Markowitz、風險平價與 Black-Litterman 的權重配置。")

# Asset selection
st.subheader("資產選擇")

col1, col2 = st.columns([3, 1])

with col1:
    assets_input = st.text_input(
        "輸入股票代碼（以逗號分隔）",
        placeholder="例如：AAPL, MSFT, GOOGL, AMZN, META",
        key="assets_input"
    )

with col2:
    lookback_years = st.selectbox(
        "回望期間",
        [1, 2, 3, 5],
        index=1,
        format_func=lambda x: f"{x} 年",
        key="lookback_years"
    )

# Optimization method
st.subheader("最佳化方法")

method = st.radio(
    "選擇方法",
    [
        "最大夏普比率 (Maximum Sharpe)",
        "最小波動 (Minimum Volatility)",
        "風險平價 (HRP)",
        "Black-Litterman 模型"
    ],
    key="opt_method"
)

# Method-specific parameters
if method == "Black-Litterman 模型":
    st.subheader("Black-Litterman 觀點")
    st.info("輸入您的市場觀點。每個觀點應指定資產的預期報酬率。")

    # Get assets for views
    if assets_input:
        assets = [a.strip().upper() for a in assets_input.split(',')]

        views = {}
        confidences = {}

        for i, asset in enumerate(assets[:5]):  # Limit to 5 assets for UI
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                has_view = st.checkbox(f"Add view for {asset}", key=f"view_check_{i}")
            with col2:
                if has_view:
                    view_return = st.number_input(
                        f"Expected return (%) for {asset}",
                        min_value=-50.0,
                        max_value=100.0,
                        value=10.0,
                        step=1.0,
                        key=f"view_return_{i}"
                    )
                    views[asset] = view_return / 100
            with col3:
                if has_view:
                    confidence = st.slider(
                        "Confidence",
                        0.1, 1.0, 0.5,
                        key=f"view_conf_{i}"
                    )
                    confidences[asset] = confidence

# Constraints
st.subheader("限制條件")
col1, col2 = st.columns(2)

with col1:
    min_weight = st.slider(
        "最小權重 (%)",
        0, 50, 0,
        key="min_weight"
    )

with col2:
    max_weight = st.slider(
        "最大權重 (%)",
        10, 100, 100,
        key="max_weight"
    )

# Investment amount for discrete allocation
st.subheader("投資金額")

total_investment = st.number_input(
    "總投資金額（元）",
    min_value=1000,
    value=100000,
    step=1000,
    key="total_investment"
)

risk_free_rate = st.number_input(
    "無風險利率 (%)",
    min_value=0.0,
    max_value=20.0,
    value=2.0,
    step=0.1,
    key="risk_free_rate"
)

# Run optimization
st.markdown("---")

col1, col2 = st.columns([1, 3])

with col1:
    run_optimization = st.button("執行最佳化", type="primary")

with col2:
    show_frontier = st.button("顯示效率前緣")

if run_optimization:
    if not assets_input:
        st.warning("請輸入至少兩個股票代碼")
    else:
        assets = [a.strip().upper() for a in assets_input.split(',')]

        if len(assets) < 2:
            st.warning("執行投資組合最佳化需要至少兩個股票代碼")
        else:
            dm = get_data_manager()
            optimizer = get_portfolio_optimizer()

            if dm and optimizer:
                # Calculate date range
                end_date = datetime.now()
                start_date = end_date - timedelta(days=365 * lookback_years)

                with st.spinner("正在取得價格資料..."):
                    # Fetch data for all assets
                    price_data = {}
                    for asset in assets:
                        try:
                            df = dm.fetch_ohlcv(
                                asset,
                                start_date.strftime('%Y-%m-%d'),
                                end_date.strftime('%Y-%m-%d')
                            )
                            if df is not None and not df.empty:
                                price_data[asset] = df['close']
                        except Exception as e:
                            st.error(f"無法取得 {asset} 的資料：{e}")

                    if len(price_data) < 2:
                        st.error("需要至少 2 個有效的資產資料")
                    else:
                        # Combine into DataFrame
                        prices_df = pd.DataFrame(price_data)
                        prices_df = prices_df.dropna()

                        if prices_df.empty or len(prices_df) < 30:
                            st.error("選定資產的重疊資料不足")
                        else:
                            st.success(f"已載入 {len(price_data)} 個資產共 {len(prices_df)} 天的資料")

                            with st.spinner("執行最佳化中..."):
                                try:
                                    # Run optimization based on method
                                    if method == "最大夏普比率 (Maximum Sharpe)":
                                        result = optimizer.max_sharpe(
                                            prices_df,
                                            risk_free_rate=risk_free_rate / 100,
                                            weight_bounds=(min_weight / 100, max_weight / 100)
                                        )
                                    elif method == "最小波動 (Minimum Volatility)":
                                        result = optimizer.min_volatility(
                                            prices_df,
                                            weight_bounds=(min_weight / 100, max_weight / 100)
                                        )
                                    elif method == "風險平價 (HRP)":
                                        result = optimizer.risk_parity(prices_df)
                                    elif method == "Black-Litterman 模型":
                                        if views:
                                            result = optimizer.black_litterman(
                                                prices_df,
                                                views=views,
                                                confidences=confidences if confidences else None,
                                                risk_free_rate=risk_free_rate / 100
                                            )
                                        else:
                                            st.warning("未指定觀點，改為使用最大夏普比率方法")
                                            result = optimizer.max_sharpe(
                                                prices_df,
                                                risk_free_rate=risk_free_rate / 100
                                            )

                                    st.session_state.optimization_result = result
                                    st.session_state.optimization_prices = prices_df
                                    st.success("最佳化已完成！")

                                except Exception as e:
                                    st.error(f"最佳化失敗：{e}")
                                    import traceback
                                    st.error(traceback.format_exc())

if show_frontier and assets_input:
    assets = [a.strip().upper() for a in assets_input.split(',')]
    dm = get_data_manager()
    optimizer = get_portfolio_optimizer()

    if dm and optimizer:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * lookback_years)

        with st.spinner("計算效率前緣中..."):
            price_data = {}
            for asset in assets:
                try:
                    df = dm.fetch_ohlcv(
                        asset,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )
                    if df is not None and not df.empty:
                        price_data[asset] = df['close']
                except Exception:
                    pass

            if len(price_data) >= 2:
                prices_df = pd.DataFrame(price_data).dropna()
                try:
                    ef_data = optimizer.efficient_frontier(
                        prices_df,
                        num_portfolios=50,
                        risk_free_rate=risk_free_rate / 100
                    )

                    if ef_data is not None and not ef_data.empty:
                        fig = plot_efficient_frontier(ef_data)
                        chart(fig)
                except Exception as e:
                    st.error(f"無法計算效率前緣：{e}")

# Results section
st.markdown("---")
st.subheader("最佳化結果")

if st.session_state.optimization_result is not None:
    result = st.session_state.optimization_result

    # Key metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "預期年報酬率",
            f"{result.expected_return:.2%}"
        )

    with col2:
        st.metric(
            "年波動率",
            f"{result.volatility:.2%}"
        )

    with col3:
        st.metric(
            "夏普比率",
            f"{result.sharpe_ratio:.2f}"
        )

    st.markdown("---")

    # Weights visualization
    col1, col2 = st.columns(2)

    with col1:
        fig = plot_weights_pie(result.weights)
        chart(fig)

    with col2:
        fig = plot_weights_bar(result.weights)
        chart(fig)

    # Weights table
    st.subheader("權重配置")

    weights_df = pd.DataFrame({
        'Asset': list(result.weights.keys()),
        'Weight (%)': [f"{v*100:.2f}%" for v in result.weights.values()],
        'Weight': list(result.weights.values())
    })
    weights_df = weights_df.sort_values('Weight', ascending=False)
    st.dataframe(weights_df[['Asset', 'Weight (%)']], width="stretch", hide_index=True)

    # Discrete allocation
    st.subheader("離散配置（實際股數）")

    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("計算離散配置"):
            optimizer = get_portfolio_optimizer()
            prices_df = st.session_state.get('optimization_prices')

            if optimizer and prices_df is not None:
                try:
                    allocation, leftover = optimizer.discrete_allocation(
                        result.weights,
                        prices_df,
                        total_investment
                    )

                    alloc_df = pd.DataFrame({
                        '資產': list(allocation.keys()),
                        '股數': list(allocation.values()),
                        '價格': [prices_df[a].iloc[-1] for a in allocation.keys()],
                        '金額': [allocation[a] * prices_df[a].iloc[-1] for a in allocation.keys()]
                    })
                    alloc_df['金額'] = [money(x, a, 0) for x, a in zip(alloc_df['金額'], alloc_df['資產'])]
                    alloc_df['價格'] = [money(x, a) for x, a in zip(alloc_df['價格'], alloc_df['資產'])]

                    st.dataframe(alloc_df, width="stretch", hide_index=True)
                    st.info(f"剩餘現金：{money(leftover, list(allocation.keys()), 0)}")

                except Exception as e:
                    st.error(f"無法計算離散配置：{e}")

    # Correlation matrix
    if 'optimization_prices' in st.session_state:
        st.subheader("相關係數矩陣")
        prices_df = st.session_state.optimization_prices
        returns = prices_df.pct_change().dropna()
        fig = plot_correlation_heatmap(returns)
        chart(fig)

    # Export
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        weights_export = pd.DataFrame({
            'Asset': list(result.weights.keys()),
            'Weight': list(result.weights.values())
        })
        csv = weights_export.to_csv(index=False)
        st.download_button(
            "下載權重",
            data=csv,
            file_name="portfolio_weights.csv",
            mime="text/csv"
        )

else:
    st.info("執行最佳化以查看結果。")

# Help section
with st.expander("方法說明"):
    st.markdown("""
    **最大夏普比率 (MSR)**
    - 找到具有最高風險調整報酬的投資組合
    - 優化超額報酬與波動率的比率
    - 適用於：平衡風險/報酬的配置

    **最小波動 (Min Vol)**
    - 找到整體風險最低的投資組合
    - 優先考慮穩定性勝於報酬
    - 適用於：保守型投資者

    **風險平價 (HRP)**
    - 分層風險平價演算法
    - 根據相關性叢集平均分配風險
    - 適用於：多樣化配置且無需報酬預測

    **Black-Litterman 模型**
    - 結合市場均衡與投資者觀點
    - 允許您表達對預期報酬的看法
    - 適用於：有市場觀點的主動型投資者
    """)
