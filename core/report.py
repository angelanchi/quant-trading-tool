# -*- coding: utf-8 -*-
"""
Report generation module.

Generates HTML and PDF reports for backtests, portfolio analysis, and risk metrics.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


@dataclass
class ReportSection:
    """A section in a report."""
    title: str
    content: str
    charts: List[str] = None  # List of chart HTML strings

    def __post_init__(self):
        if self.charts is None:
            self.charts = []


class ReportGenerator:
    """
    Generate comprehensive trading reports.

    Supports:
    - Backtest performance reports
    - Portfolio analysis reports
    - Risk analysis reports
    - Combined multi-strategy comparison reports
    """

    def __init__(self, title: str = "Quantitative Trading Report"):
        self.title = title
        self.sections: List[ReportSection] = []
        self.metadata: Dict[str, Any] = {
            'generated_at': datetime.now().isoformat(),
            'generator': 'Quantitative Trading Tool'
        }

    def add_section(self, title: str, content: str, charts: List[str] = None):
        """Add a section to the report."""
        self.sections.append(ReportSection(title, content, charts or []))

    def _generate_style(self) -> str:
        """Generate CSS styles for the report."""
        return """
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .report-container {
                background-color: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #1a1a2e;
                border-bottom: 3px solid #4a90d9;
                padding-bottom: 10px;
            }
            h2 {
                color: #16213e;
                margin-top: 30px;
                border-left: 4px solid #4a90d9;
                padding-left: 10px;
            }
            h3 {
                color: #0f3460;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #4a90d9;
                color: white;
            }
            tr:hover {
                background-color: #f5f5f5;
            }
            .metric-card {
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                margin: 10px;
                border-radius: 8px;
                min-width: 150px;
                text-align: center;
            }
            .metric-value {
                font-size: 24px;
                font-weight: bold;
            }
            .metric-label {
                font-size: 12px;
                opacity: 0.9;
            }
            .positive { color: #27ae60; }
            .negative { color: #e74c3c; }
            .neutral { color: #7f8c8d; }
            .chart-container {
                margin: 20px 0;
                padding: 10px;
                background-color: #fafafa;
                border-radius: 4px;
            }
            .summary-box {
                background-color: #e8f4f8;
                padding: 15px;
                border-radius: 4px;
                margin: 15px 0;
            }
            .footer {
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #666;
                text-align: center;
            }
        </style>
        """

    def _format_number(self, value: float, format_type: str = 'number') -> str:
        """Format a number for display."""
        if pd.isna(value) or not np.isfinite(value):
            return "N/A"

        if format_type == 'percent':
            return f"{value:.2%}"
        elif format_type == 'ratio':
            return f"{value:.2f}"
        elif format_type == 'currency':
            return f"${value:,.2f}"
        elif format_type == 'integer':
            return f"{int(value):,}"
        else:
            return f"{value:.4f}"

    def _color_class(self, value: float, reverse: bool = False) -> str:
        """Get CSS class based on value sign."""
        if pd.isna(value):
            return 'neutral'
        if reverse:
            return 'negative' if value > 0 else 'positive' if value < 0 else 'neutral'
        return 'positive' if value > 0 else 'negative' if value < 0 else 'neutral'

    def generate_backtest_report(
        self,
        result,
        strategy_name: str = "Strategy",
        symbols: List[str] = None,
        parameters: Dict = None
    ) -> 'ReportGenerator':
        """
        Generate a backtest performance report.

        Args:
            result: BacktestResult object
            strategy_name: Name of the strategy
            symbols: List of traded symbols
            parameters: Strategy parameters

        Returns:
            self for chaining
        """
        # Summary section
        summary_html = f"""
        <div class="summary-box">
            <strong>Strategy:</strong> {strategy_name}<br>
            <strong>Symbols:</strong> {', '.join(symbols) if symbols else 'N/A'}<br>
            <strong>Parameters:</strong> {json.dumps(parameters) if parameters else 'Default'}
        </div>

        <div style="display: flex; flex-wrap: wrap; justify-content: center;">
            <div class="metric-card">
                <div class="metric-value">{self._format_number(result.total_return, 'percent')}</div>
                <div class="metric-label">Total Return</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{self._format_number(result.cagr, 'percent')}</div>
                <div class="metric-label">CAGR</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{self._format_number(result.sharpe_ratio, 'ratio')}</div>
                <div class="metric-label">Sharpe Ratio</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{self._format_number(result.max_drawdown, 'percent')}</div>
                <div class="metric-label">Max Drawdown</div>
            </div>
        </div>
        """

        self.add_section("Performance Summary", summary_html)

        # Detailed metrics table
        metrics_html = """
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
        """

        metrics = [
            ("Total Return", result.total_return, 'percent'),
            ("CAGR", result.cagr, 'percent'),
            ("Sharpe Ratio", result.sharpe_ratio, 'ratio'),
            ("Sortino Ratio", result.sortino_ratio, 'ratio'),
            ("Calmar Ratio", result.calmar_ratio, 'ratio'),
            ("Max Drawdown", result.max_drawdown, 'percent'),
            ("Total Trades", result.total_trades, 'integer'),
            ("Win Rate", result.win_rate, 'percent'),
            ("Profit Factor", result.profit_factor, 'ratio'),
        ]

        for name, value, fmt in metrics:
            color = self._color_class(value) if fmt == 'percent' else ''
            formatted = self._format_number(value, fmt)
            metrics_html += f'<tr><td>{name}</td><td class="{color}">{formatted}</td></tr>'

        metrics_html += "</table>"

        self.add_section("Detailed Metrics", metrics_html)

        # Equity curve chart
        if PLOTLY_AVAILABLE and result.equity_curve is not None:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=result.equity_curve.index,
                y=result.equity_curve.values,
                mode='lines',
                name='Portfolio Value',
                line=dict(color='#4a90d9', width=2)
            ))
            fig.update_layout(
                title='Equity Curve',
                xaxis_title='Date',
                yaxis_title='Portfolio Value',
                template='plotly_white',
                height=400
            )
            chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
            self.add_section("Equity Curve", "", [chart_html])

        return self

    def generate_risk_report(self, metrics, returns: pd.Series = None) -> 'ReportGenerator':
        """
        Generate a risk analysis report.

        Args:
            metrics: RiskMetrics object
            returns: Optional returns series for charts

        Returns:
            self for chaining
        """
        # Risk metrics summary
        risk_html = """
        <table>
            <tr><th>Risk Metric</th><th>Value</th></tr>
        """

        risk_items = [
            ("VaR (95% Historical)", metrics.var_95_historical, 'percent'),
            ("VaR (99% Historical)", metrics.var_99_historical, 'percent'),
            ("VaR (95% Parametric)", metrics.var_95_parametric, 'percent'),
            ("CVaR (95%)", metrics.cvar_95, 'percent'),
            ("Volatility (Annual)", metrics.volatility, 'percent'),
            ("Downside Deviation", metrics.downside_deviation, 'percent'),
            ("Max Drawdown", metrics.max_drawdown, 'percent'),
            ("Skewness", metrics.skewness, 'ratio'),
            ("Kurtosis", metrics.kurtosis, 'ratio'),
        ]

        for name, value, fmt in risk_items:
            formatted = self._format_number(value, fmt)
            risk_html += f'<tr><td>{name}</td><td>{formatted}</td></tr>'

        risk_html += "</table>"

        self.add_section("Risk Metrics", risk_html)

        # Return distribution chart
        if PLOTLY_AVAILABLE and returns is not None:
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=returns,
                nbinsx=50,
                name='Returns',
                marker_color='#4a90d9'
            ))

            # Add VaR lines
            var_95 = metrics.var_95_historical
            fig.add_vline(x=var_95, line_dash="dash", line_color="red",
                         annotation_text=f"VaR 95%: {var_95:.2%}")

            fig.update_layout(
                title='Return Distribution',
                xaxis_title='Daily Return',
                yaxis_title='Frequency',
                template='plotly_white',
                height=400
            )
            chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
            self.add_section("Return Distribution", "", [chart_html])

        return self

    def generate_portfolio_report(
        self,
        result,
        method: str = "Optimization"
    ) -> 'ReportGenerator':
        """
        Generate a portfolio optimization report.

        Args:
            result: OptimizationResult object
            method: Optimization method name

        Returns:
            self for chaining
        """
        # Portfolio summary
        summary_html = f"""
        <div class="summary-box">
            <strong>Method:</strong> {method}<br>
            <strong>Expected Return:</strong> {self._format_number(result.expected_return, 'percent')}<br>
            <strong>Expected Volatility:</strong> {self._format_number(result.volatility, 'percent')}<br>
            <strong>Sharpe Ratio:</strong> {self._format_number(result.sharpe_ratio, 'ratio')}
        </div>
        """

        self.add_section("Portfolio Summary", summary_html)

        # Weights table
        weights_html = """
        <table>
            <tr><th>Asset</th><th>Weight</th></tr>
        """

        for asset, weight in sorted(result.weights.items(), key=lambda x: -x[1]):
            if weight > 0.001:
                weights_html += f'<tr><td>{asset}</td><td>{self._format_number(weight, "percent")}</td></tr>'

        weights_html += "</table>"

        self.add_section("Asset Allocation", weights_html)

        # Pie chart
        if PLOTLY_AVAILABLE:
            weights = {k: v for k, v in result.weights.items() if v > 0.01}
            fig = go.Figure(data=[go.Pie(
                labels=list(weights.keys()),
                values=list(weights.values()),
                hole=0.4,
                marker_colors=['#4a90d9', '#667eea', '#764ba2', '#f093fb', '#f5576c']
            )])
            fig.update_layout(
                title='Portfolio Allocation',
                template='plotly_white',
                height=400
            )
            chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
            self.add_section("Allocation Chart", "", [chart_html])

        return self

    def to_html(self) -> str:
        """Generate the complete HTML report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{self.title}</title>
            {self._generate_style()}
        </head>
        <body>
            <div class="report-container">
                <h1>{self.title}</h1>
                <p><em>Generated: {self.metadata['generated_at']}</em></p>
        """

        for section in self.sections:
            html += f"""
                <h2>{section.title}</h2>
                {section.content}
            """
            for chart in section.charts:
                html += f'<div class="chart-container">{chart}</div>'

        html += f"""
                <div class="footer">
                    Generated by {self.metadata['generator']}
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def save(self, filepath: str):
        """Save the report to a file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        html_content = self.to_html()

        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Report saved to: {path}")
        return path


def generate_backtest_report(
    result,
    strategy_name: str,
    symbols: List[str] = None,
    parameters: Dict = None,
    output_path: str = None
) -> str:
    """
    Convenience function to generate a backtest report.

    Args:
        result: BacktestResult object
        strategy_name: Name of the strategy
        symbols: List of symbols
        parameters: Strategy parameters
        output_path: Optional path to save the report

    Returns:
        HTML string of the report
    """
    report = ReportGenerator(f"Backtest Report - {strategy_name}")
    report.generate_backtest_report(result, strategy_name, symbols, parameters)

    if output_path:
        report.save(output_path)

    return report.to_html()


def generate_full_report(
    backtest_result=None,
    risk_metrics=None,
    portfolio_result=None,
    returns: pd.Series = None,
    title: str = "Quantitative Analysis Report",
    output_path: str = None
) -> str:
    """
    Generate a comprehensive report with all analyses.

    Args:
        backtest_result: BacktestResult object
        risk_metrics: RiskMetrics object
        portfolio_result: OptimizationResult object
        returns: Returns series
        title: Report title
        output_path: Optional path to save

    Returns:
        HTML string
    """
    report = ReportGenerator(title)

    if backtest_result:
        report.generate_backtest_report(backtest_result)

    if risk_metrics:
        report.generate_risk_report(risk_metrics, returns)

    if portfolio_result:
        report.generate_portfolio_report(portfolio_result)

    if output_path:
        report.save(output_path)

    return report.to_html()
