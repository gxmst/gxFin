import pandas as pd
import numpy as np
from datetime import datetime

class LightBacktester:
    """
    Minimal memory-only backtest engine.
    Does not touch the database.

    CANONICAL EXECUTION MODEL ("Next-Bar-Open Sandbox"):
    This tester mathematically executes orders at `next_bar['open']`. 
    In the live system, the Runner evaluates signals upon confirming a bar close, 
    and immediately fires `fetch_ticker()` to approximate this target price.
    
    WARNING: While structurally aligned, live execution via `fetch_ticker()` 
    is NOT identical to the idealized `next_bar['open']`. Live results will differ 
    due to thin order books, opening gaps, API delays, and fast market moves 
    immediately following the bar close. Backtests should be treated as 
    directional simulations, not exact equivalents.
    """
    def __init__(self, initial_balance=100000, pessimism_factor=0.002):
        self.initial_balance = initial_balance
        self.pessimism_factor = pessimism_factor

    def run(self, strategy, df: pd.DataFrame):
        """
        Run strategy over a DataFrame.
        Returns a dictionary of performance metrics.
        """
        balance = self.initial_balance
        position_qty = 0
        position_avg_price = 0
        trades = []
        equity_curve = [balance]
        
        # We start from bar slow_period to ensure indicators are ready
        # BUT we must execute on the NEXT bar's Open if a signal is generated at i
        for i in range(1, len(df) - 1):
            current_df = df.iloc[:i+1]
            signal = strategy.generate_signal(current_df)
            
            # The execution price is the OPEN of the NEXT bar (i+1)
            # This is the most realistic simulation of a signal detected at close
            next_bar = df.iloc[i+1]
            price = next_bar['open']
            
            if signal == 'BUY' and position_qty == 0:
                execution_price = price * (1 + self.pessimism_factor)
                position_qty = balance / execution_price
                position_avg_price = execution_price
                balance = 0
                trades.append({'action': 'BUY', 'price': execution_price, 'time': next_bar['timestamp']})
                
            elif signal == 'SELL' and position_qty > 0:
                execution_price = price * (1 - self.pessimism_factor)
                balance = position_qty * execution_price
                position_qty = 0
                trades.append({'action': 'SELL', 'price': execution_price, 'time': next_bar['timestamp']})
                
            # Current Equity based on next bar's CLOSE for tracking
            current_equity = balance + (position_qty * next_bar['close'])
            equity_curve.append(current_equity)

        # Performance Calculations
        equity_curve = np.array(equity_curve)
        total_return = (equity_curve[-1] - self.initial_balance) / self.initial_balance
        
        # Drawdown
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak
        max_drawdown = np.max(drawdown)
        
        # Win Rate
        trade_pairs = []
        for i in range(0, len(trades)-1, 2):
            if trades[i]['action'] == 'BUY' and trades[i+1]['action'] == 'SELL':
                pnl = (trades[i+1]['price'] - trades[i]['price']) / trades[i]['price']
                trade_pairs.append(pnl)
        
        win_rate = np.mean(np.array(trade_pairs) > 0) if trade_pairs else 0
        
        # Sharpe (Simplified Daily approximation)
        returns = np.diff(equity_curve) / equity_curve[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

        return {
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'sharpe': sharpe,
            'trade_count': len(trade_pairs),
            'equity_curve': equity_curve,
            'final_balance': equity_curve[-1]
        }
