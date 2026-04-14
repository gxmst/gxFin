import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..storage.database import AccountState, TradeHistory

class MockBroker:
    """
    Simulation engine for order execution.
    Applies fees and slippage via a single 'pessimism factor'.
    """
    
    def __init__(self, db_session: Session, pessimism_factor: float = 0.002):
        self.db = db_session
        self.pessimism_factor = pessimism_factor  # Default 0.2%
        self.logger = logging.getLogger(__name__)

    def _get_account(self) -> AccountState:
        return self.db.query(AccountState).order_by(AccountState.id.desc()).first()

    def execute_order(self, action: str, symbol: str, price: float, strategy_name: str):
        """
        Execute a simulated order.
        action: 'BUY' or 'SELL'
        """
        account = self._get_account()
        if not account:
            self.logger.error("No account state found.")
            return

        if action == 'BUY':
            if account.balance <= 0:
                self.logger.warning("Insufficient funds for BUY signal.")
                return
            
            # Apply pessimism: Price gets HIGHER when buying
            execution_price = price * (1 + self.pessimism_factor)
            
            # Full position buy
            qty = account.balance / execution_price
            
            # Precision check: don't buy if the amount is too tiny ($1 equivalent)
            if account.balance < 1.0:
                self.logger.warning(f"Balance {account.balance} too low for meaningful BUY.")
                return

            cost = account.balance
            
            # Update account
            account.position_qty += qty
            # Simple weighted average for cost
            total_cost = (account.position_qty - qty) * account.position_avg_price + cost
            account.position_avg_price = total_cost / account.position_qty
            account.balance = 0
            
            self._record_trade(strategy_name, symbol, 'BUY', execution_price, qty, cost)
            
        elif action == 'SELL':
            if account.position_qty <= 0:
                self.logger.warning("No position to SELL.")
                return
            
            # Apply pessimism: Price gets LOWER when selling
            execution_price = price * (1 - self.pessimism_factor)
            
            qty = account.position_qty
            revenue = qty * execution_price
            
            # Calculate realized PnL
            profit = (execution_price - account.position_avg_price) * qty
            account.realized_pnl += profit
            
            # Update account
            account.balance += revenue
            account.position_qty = 0
            account.position_avg_price = 0
            
            self._record_trade(strategy_name, symbol, 'SELL', execution_price, qty, revenue)

        self.db.commit()

    def _record_trade(self, strategy_name, symbol, action, price, qty, total_cost):
        trade = TradeHistory(
            strategy_name=strategy_name,
            symbol=symbol,
            action=action,
            price=price,
            qty=qty,
            total_cost=total_cost,
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        self.db.add(trade)
        self.logger.info(f"Simulated {action} at {price:.4f} for {symbol}. Qty: {qty:.4f}")
