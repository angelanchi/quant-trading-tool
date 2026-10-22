# -*- coding: utf-8 -*-
"""
Alert system example for quantitative trading tool.

Demonstrates:
- Creating price alerts
- Creating signal alerts
- Handling alert events
- Monitoring positions

Usage:
    python examples/alerts_example.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from datetime import datetime


def example_price_alerts():
    """Example: Price level alerts."""
    print("\n" + "=" * 60)
    print("Example 1: Price Level Alerts")
    print("=" * 60)

    from core import AlertManager, AlertPriority, console_alert_handler

    # Create alert manager
    manager = AlertManager()

    # Add console handler to see alerts
    manager.add_handler(console_alert_handler)

    # Create price alerts
    print("\nCreating price alerts...")

    alert1 = manager.create_price_alert(
        symbol='AAPL',
        price=150.0,
        direction='above',
        priority=AlertPriority.HIGH
    )
    print(f"  Created: {alert1.name}")

    alert2 = manager.create_price_alert(
        symbol='AAPL',
        price=140.0,
        direction='below',
        priority=AlertPriority.MEDIUM
    )
    print(f"  Created: {alert2.name}")

    # Simulate price updates
    print("\nSimulating price updates...")
    prices = [145.0, 148.0, 151.0, 149.0, 138.0]

    for price in prices:
        print(f"\n  AAPL current price: ${price:.2f}")
        manager.check_price_alerts('AAPL', price)


def example_change_alerts():
    """Example: Percentage change alerts."""
    print("\n" + "=" * 60)
    print("Example 2: Percentage Change Alerts")
    print("=" * 60)

    from core import AlertManager, AlertPriority, console_alert_handler

    manager = AlertManager()
    manager.add_handler(console_alert_handler)

    # Create change alerts
    print("\nCreating change alerts...")

    alert = manager.create_change_alert(
        symbol='MSFT',
        change_pct=0.03,  # 3%
        direction='any',
        priority=AlertPriority.HIGH
    )
    print(f"  Created: {alert.name}")

    # Simulate price changes
    print("\nSimulating price changes...")
    price_pairs = [
        (300.0, 305.0),   # +1.67%
        (305.0, 295.0),   # -3.28% -> Alert!
        (295.0, 310.0),   # +5.08% -> Alert!
    ]

    for prev, curr in price_pairs:
        change = (curr - prev) / prev
        print(f"\n  MSFT: ${prev:.2f} -> ${curr:.2f} ({change:+.2%})")
        manager.check_change_alerts('MSFT', curr, prev)


def example_signal_alerts():
    """Example: Trading signal alerts."""
    print("\n" + "=" * 60)
    print("Example 3: Trading Signal Alerts")
    print("=" * 60)

    from core import AlertManager, AlertPriority, console_alert_handler

    manager = AlertManager()
    manager.add_handler(console_alert_handler)

    # Create signal alerts
    print("\nCreating signal alerts...")

    alert1 = manager.create_signal_alert(
        symbol='GOOGL',
        strategy_name='MeanReversion',
        signal_type='buy',
        priority=AlertPriority.HIGH
    )
    print(f"  Created: {alert1.name}")

    alert2 = manager.create_signal_alert(
        symbol='GOOGL',
        strategy_name='MeanReversion',
        signal_type='sell',
        priority=AlertPriority.HIGH
    )
    print(f"  Created: {alert2.name}")

    # Simulate signals
    print("\nSimulating trading signals...")
    signals = [
        (0, "Neutral"),
        (1, "Buy"),
        (0, "Neutral"),
        (-1, "Sell"),
    ]

    for signal, label in signals:
        print(f"\n  MeanReversion signal for GOOGL: {label}")
        manager.check_signal_alerts('GOOGL', 'MeanReversion', signal)


def example_drawdown_alerts():
    """Example: Drawdown alerts."""
    print("\n" + "=" * 60)
    print("Example 4: Drawdown Alerts")
    print("=" * 60)

    from core import AlertManager, AlertPriority, console_alert_handler

    manager = AlertManager()
    manager.add_handler(console_alert_handler)

    # Create drawdown alert
    print("\nCreating drawdown alert...")

    alert = manager.create_drawdown_alert(
        symbol='portfolio',
        max_drawdown=-0.10,  # -10%
        priority=AlertPriority.CRITICAL
    )
    print(f"  Created: {alert.name}")

    # Simulate drawdowns
    print("\nSimulating portfolio drawdowns...")
    drawdowns = [-0.02, -0.05, -0.08, -0.12, -0.15]

    for dd in drawdowns:
        print(f"\n  Portfolio drawdown: {dd:.2%}")
        manager.check_drawdown_alert('portfolio', dd)


def example_custom_handler():
    """Example: Custom alert handler."""
    print("\n" + "=" * 60)
    print("Example 5: Custom Alert Handler")
    print("=" * 60)

    from core import AlertManager, AlertEvent, AlertPriority

    manager = AlertManager()

    # Create custom handler that logs to a list
    alert_log = []

    def custom_handler(event: AlertEvent):
        alert_log.append({
            'time': event.triggered_at.strftime('%H:%M:%S'),
            'alert': event.alert.name,
            'value': event.current_value,
            'message': event.message
        })
        print(f"  [LOGGED] {event.alert.name}")

    manager.add_handler(custom_handler)

    # Create and trigger some alerts
    print("\nCreating alerts with custom handler...")

    manager.create_price_alert('AAPL', 150.0, 'above')
    manager.create_price_alert('AAPL', 140.0, 'below')

    # Trigger alerts
    manager.check_price_alerts('AAPL', 155.0)
    manager.check_price_alerts('AAPL', 135.0)

    # Show log
    print(f"\n--- Alert Log ({len(alert_log)} entries) ---")
    for entry in alert_log:
        print(f"  [{entry['time']}] {entry['alert']}: {entry['message']}")


def example_alert_management():
    """Example: Managing alerts."""
    print("\n" + "=" * 60)
    print("Example 6: Alert Management")
    print("=" * 60)

    from core import AlertManager

    manager = AlertManager()

    # Create multiple alerts
    print("\nCreating alerts...")
    alerts = []
    for symbol in ['AAPL', 'MSFT', 'GOOGL']:
        alert = manager.create_price_alert(symbol, 100.0, 'above')
        alerts.append(alert)
        print(f"  Created: {alert.id} - {alert.name}")

    # List alerts for a symbol
    print(f"\nAlerts for AAPL:")
    for alert in manager.get_alerts_for_symbol('AAPL'):
        print(f"  - {alert.name} (enabled: {alert.enabled})")

    # Disable an alert
    print(f"\nDisabling alert: {alerts[0].id}")
    manager.disable_alert(alerts[0].id)
    print(f"  Alert enabled: {alerts[0].enabled}")

    # Export alerts
    print("\nExporting alerts to JSON...")
    json_str = manager.export_alerts()
    print(f"  Exported {len(manager.alerts)} alerts")
    print(f"  JSON preview: {json_str[:100]}...")

    # Remove an alert
    print(f"\nRemoving alert: {alerts[1].id}")
    manager.remove_alert(alerts[1].id)
    print(f"  Remaining alerts: {len(manager.alerts)}")


def main():
    """Run all alert examples."""
    print("\n" + "#" * 60)
    print("# Quantitative Trading Tool - Alert System Examples")
    print("#" * 60)

    # Example 1: Price alerts
    example_price_alerts()

    # Example 2: Change alerts
    example_change_alerts()

    # Example 3: Signal alerts
    example_signal_alerts()

    # Example 4: Drawdown alerts
    example_drawdown_alerts()

    # Example 5: Custom handler
    example_custom_handler()

    # Example 6: Alert management
    example_alert_management()

    print("\n" + "#" * 60)
    print("# Alert system examples completed!")
    print("#" * 60)


if __name__ == "__main__":
    main()
