# -*- coding: utf-8 -*-
"""
Alert and notification system.

Monitors price levels, signals, and risk metrics,
triggering alerts when conditions are met.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CHANGE_PCT = "price_change_pct"
    SIGNAL = "signal"
    DRAWDOWN = "drawdown"
    VAR_BREACH = "var_breach"
    CUSTOM = "custom"


class AlertPriority(Enum):
    """Alert priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents an alert configuration."""
    id: str
    name: str
    alert_type: AlertType
    symbol: str
    condition: Dict[str, Any]
    priority: AlertPriority = AlertPriority.MEDIUM
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    cooldown_seconds: int = 3600  # 1 hour default cooldown

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'alert_type': self.alert_type.value,
            'symbol': self.symbol,
            'condition': self.condition,
            'priority': self.priority.value,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'last_triggered': self.last_triggered.isoformat() if self.last_triggered else None,
            'trigger_count': self.trigger_count,
            'cooldown_seconds': self.cooldown_seconds
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Alert':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            alert_type=AlertType(data['alert_type']),
            symbol=data['symbol'],
            condition=data['condition'],
            priority=AlertPriority(data.get('priority', 'medium')),
            enabled=data.get('enabled', True),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            last_triggered=datetime.fromisoformat(data['last_triggered']) if data.get('last_triggered') else None,
            trigger_count=data.get('trigger_count', 0),
            cooldown_seconds=data.get('cooldown_seconds', 3600)
        )


@dataclass
class AlertEvent:
    """Represents a triggered alert event."""
    alert: Alert
    triggered_at: datetime
    current_value: Any
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'alert_id': self.alert.id,
            'alert_name': self.alert.name,
            'symbol': self.alert.symbol,
            'priority': self.alert.priority.value,
            'triggered_at': self.triggered_at.isoformat(),
            'current_value': self.current_value,
            'message': self.message,
            'data': self.data
        }


class AlertManager:
    """
    Manages alert configurations and monitors conditions.

    Features:
    - Price level alerts
    - Percentage change alerts
    - Signal-based alerts
    - Risk metric alerts (drawdown, VaR)
    - Custom condition alerts
    - Cooldown to prevent spam
    """

    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.handlers: List[Callable[[AlertEvent], None]] = []
        self.event_history: List[AlertEvent] = []
        self._next_id = 1

    def _generate_id(self) -> str:
        """Generate a unique alert ID."""
        alert_id = f"alert_{self._next_id}"
        self._next_id += 1
        return alert_id

    def add_handler(self, handler: Callable[[AlertEvent], None]):
        """Add an alert event handler."""
        self.handlers.append(handler)

    def remove_handler(self, handler: Callable[[AlertEvent], None]):
        """Remove an alert event handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)

    def create_price_alert(
        self,
        symbol: str,
        price: float,
        direction: str = 'above',
        name: str = None,
        priority: AlertPriority = AlertPriority.MEDIUM
    ) -> Alert:
        """
        Create a price level alert.

        Args:
            symbol: Stock symbol
            price: Target price level
            direction: 'above' or 'below'
            name: Alert name
            priority: Alert priority

        Returns:
            Created Alert object
        """
        alert_type = AlertType.PRICE_ABOVE if direction == 'above' else AlertType.PRICE_BELOW
        alert = Alert(
            id=self._generate_id(),
            name=name or f"{symbol} price {direction} {price}",
            alert_type=alert_type,
            symbol=symbol,
            condition={'price': price, 'direction': direction},
            priority=priority
        )
        self.alerts[alert.id] = alert
        logger.info(f"Created price alert: {alert.name}")
        return alert

    def create_change_alert(
        self,
        symbol: str,
        change_pct: float,
        direction: str = 'any',
        timeframe: str = '1D',
        name: str = None,
        priority: AlertPriority = AlertPriority.MEDIUM
    ) -> Alert:
        """
        Create a percentage change alert.

        Args:
            symbol: Stock symbol
            change_pct: Change percentage threshold (e.g., 0.05 for 5%)
            direction: 'up', 'down', or 'any'
            timeframe: Time period for change
            name: Alert name
            priority: Alert priority

        Returns:
            Created Alert object
        """
        alert = Alert(
            id=self._generate_id(),
            name=name or f"{symbol} {change_pct:.1%} change ({direction})",
            alert_type=AlertType.PRICE_CHANGE_PCT,
            symbol=symbol,
            condition={
                'change_pct': change_pct,
                'direction': direction,
                'timeframe': timeframe
            },
            priority=priority
        )
        self.alerts[alert.id] = alert
        logger.info(f"Created change alert: {alert.name}")
        return alert

    def create_signal_alert(
        self,
        symbol: str,
        strategy_name: str,
        signal_type: str = 'any',
        name: str = None,
        priority: AlertPriority = AlertPriority.HIGH
    ) -> Alert:
        """
        Create a trading signal alert.

        Args:
            symbol: Stock symbol
            strategy_name: Strategy generating signals
            signal_type: 'buy', 'sell', or 'any'
            name: Alert name
            priority: Alert priority

        Returns:
            Created Alert object
        """
        alert = Alert(
            id=self._generate_id(),
            name=name or f"{symbol} {strategy_name} {signal_type} signal",
            alert_type=AlertType.SIGNAL,
            symbol=symbol,
            condition={
                'strategy': strategy_name,
                'signal_type': signal_type
            },
            priority=priority
        )
        self.alerts[alert.id] = alert
        logger.info(f"Created signal alert: {alert.name}")
        return alert

    def create_drawdown_alert(
        self,
        symbol: str,
        max_drawdown: float,
        name: str = None,
        priority: AlertPriority = AlertPriority.HIGH
    ) -> Alert:
        """
        Create a drawdown alert.

        Args:
            symbol: Stock symbol or 'portfolio'
            max_drawdown: Drawdown threshold (e.g., -0.10 for -10%)
            name: Alert name
            priority: Alert priority

        Returns:
            Created Alert object
        """
        alert = Alert(
            id=self._generate_id(),
            name=name or f"{symbol} drawdown exceeds {max_drawdown:.1%}",
            alert_type=AlertType.DRAWDOWN,
            symbol=symbol,
            condition={'max_drawdown': max_drawdown},
            priority=priority
        )
        self.alerts[alert.id] = alert
        logger.info(f"Created drawdown alert: {alert.name}")
        return alert

    def create_custom_alert(
        self,
        symbol: str,
        condition_func: Callable[[Dict], bool],
        name: str,
        priority: AlertPriority = AlertPriority.MEDIUM
    ) -> Alert:
        """
        Create a custom condition alert.

        Args:
            symbol: Stock symbol
            condition_func: Function that returns True when alert should trigger
            name: Alert name
            priority: Alert priority

        Returns:
            Created Alert object
        """
        alert = Alert(
            id=self._generate_id(),
            name=name,
            alert_type=AlertType.CUSTOM,
            symbol=symbol,
            condition={'func': condition_func},
            priority=priority
        )
        self.alerts[alert.id] = alert
        logger.info(f"Created custom alert: {alert.name}")
        return alert

    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert by ID."""
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            logger.info(f"Removed alert: {alert_id}")
            return True
        return False

    def enable_alert(self, alert_id: str) -> bool:
        """Enable an alert."""
        if alert_id in self.alerts:
            self.alerts[alert_id].enabled = True
            return True
        return False

    def disable_alert(self, alert_id: str) -> bool:
        """Disable an alert."""
        if alert_id in self.alerts:
            self.alerts[alert_id].enabled = False
            return True
        return False

    def _check_cooldown(self, alert: Alert) -> bool:
        """Check if alert is in cooldown period."""
        if alert.last_triggered is None:
            return False

        elapsed = (datetime.now() - alert.last_triggered).total_seconds()
        return elapsed < alert.cooldown_seconds

    def _trigger_alert(self, alert: Alert, current_value: Any, message: str, data: Dict = None):
        """Trigger an alert and notify handlers."""
        if self._check_cooldown(alert):
            logger.debug(f"Alert {alert.id} in cooldown, skipping")
            return

        event = AlertEvent(
            alert=alert,
            triggered_at=datetime.now(),
            current_value=current_value,
            message=message,
            data=data or {}
        )

        alert.last_triggered = event.triggered_at
        alert.trigger_count += 1

        self.event_history.append(event)

        # Notify all handlers
        for handler in self.handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")

        logger.info(f"Alert triggered: {alert.name} - {message}")

    def check_price_alerts(self, symbol: str, current_price: float):
        """
        Check price alerts for a symbol.

        Args:
            symbol: Stock symbol
            current_price: Current price
        """
        for alert in self.alerts.values():
            if not alert.enabled or alert.symbol != symbol:
                continue

            if alert.alert_type == AlertType.PRICE_ABOVE:
                if current_price >= alert.condition['price']:
                    self._trigger_alert(
                        alert,
                        current_price,
                        f"{symbol} price ${current_price:.2f} is above ${alert.condition['price']:.2f}"
                    )

            elif alert.alert_type == AlertType.PRICE_BELOW:
                if current_price <= alert.condition['price']:
                    self._trigger_alert(
                        alert,
                        current_price,
                        f"{symbol} price ${current_price:.2f} is below ${alert.condition['price']:.2f}"
                    )

    def check_change_alerts(self, symbol: str, current_price: float, previous_price: float):
        """
        Check percentage change alerts.

        Args:
            symbol: Stock symbol
            current_price: Current price
            previous_price: Previous price
        """
        if previous_price == 0:
            return

        change_pct = (current_price - previous_price) / previous_price

        for alert in self.alerts.values():
            if not alert.enabled or alert.symbol != symbol:
                continue

            if alert.alert_type != AlertType.PRICE_CHANGE_PCT:
                continue

            threshold = alert.condition['change_pct']
            direction = alert.condition['direction']

            triggered = False
            if direction == 'up' and change_pct >= threshold:
                triggered = True
            elif direction == 'down' and change_pct <= -threshold:
                triggered = True
            elif direction == 'any' and abs(change_pct) >= threshold:
                triggered = True

            if triggered:
                self._trigger_alert(
                    alert,
                    change_pct,
                    f"{symbol} changed {change_pct:+.2%} (threshold: {threshold:.2%})",
                    {'current_price': current_price, 'previous_price': previous_price}
                )

    def check_signal_alerts(self, symbol: str, strategy_name: str, signal: int):
        """
        Check trading signal alerts.

        Args:
            symbol: Stock symbol
            strategy_name: Strategy name
            signal: Signal value (1=buy, -1=sell, 0=neutral)
        """
        for alert in self.alerts.values():
            if not alert.enabled or alert.symbol != symbol:
                continue

            if alert.alert_type != AlertType.SIGNAL:
                continue

            if alert.condition['strategy'] != strategy_name:
                continue

            signal_type = alert.condition['signal_type']

            triggered = False
            signal_str = ""
            if signal_type == 'buy' and signal == 1:
                triggered = True
                signal_str = "BUY"
            elif signal_type == 'sell' and signal == -1:
                triggered = True
                signal_str = "SELL"
            elif signal_type == 'any' and signal != 0:
                triggered = True
                signal_str = "BUY" if signal == 1 else "SELL"

            if triggered:
                self._trigger_alert(
                    alert,
                    signal,
                    f"{strategy_name} generated {signal_str} signal for {symbol}"
                )

    def check_drawdown_alert(self, symbol: str, current_drawdown: float):
        """
        Check drawdown alerts.

        Args:
            symbol: Stock symbol or 'portfolio'
            current_drawdown: Current drawdown (negative value)
        """
        for alert in self.alerts.values():
            if not alert.enabled or alert.symbol != symbol:
                continue

            if alert.alert_type != AlertType.DRAWDOWN:
                continue

            threshold = alert.condition['max_drawdown']

            if current_drawdown <= threshold:
                self._trigger_alert(
                    alert,
                    current_drawdown,
                    f"{symbol} drawdown {current_drawdown:.2%} exceeds threshold {threshold:.2%}"
                )

    def get_recent_events(self, limit: int = 10) -> List[AlertEvent]:
        """Get recent alert events."""
        return self.event_history[-limit:]

    def get_alerts_for_symbol(self, symbol: str) -> List[Alert]:
        """Get all alerts for a symbol."""
        return [a for a in self.alerts.values() if a.symbol == symbol]

    def export_alerts(self) -> str:
        """Export alerts to JSON string."""
        return json.dumps([a.to_dict() for a in self.alerts.values()], indent=2)

    def import_alerts(self, json_str: str):
        """Import alerts from JSON string."""
        data = json.loads(json_str)
        for alert_data in data:
            alert = Alert.from_dict(alert_data)
            self.alerts[alert.id] = alert
            self._next_id = max(self._next_id, int(alert.id.split('_')[1]) + 1)


# Default console handler
def console_alert_handler(event: AlertEvent):
    """Print alert to console."""
    priority_emoji = {
        AlertPriority.LOW: "[LOW]",
        AlertPriority.MEDIUM: "[MED]",
        AlertPriority.HIGH: "[HIGH]",
        AlertPriority.CRITICAL: "[CRITICAL]"
    }

    prefix = priority_emoji.get(event.alert.priority, "")
    print(f"\n{prefix} ALERT: {event.message}")
    print(f"    Time: {event.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    Value: {event.current_value}")
