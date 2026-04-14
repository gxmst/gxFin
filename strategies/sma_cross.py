import pandas as pd
from app.strategy.base_strategy import BaseStrategy

class SmaCrossStrategy(BaseStrategy):
    """
    Simple Moving Average Crossover Strategy.
    """
    name = "SMA_Cross"
    
    def __init__(self, name="SMA_Cross", params=None):
        default_params = {'fast_period': 10, 'slow_period': 30}
        if params:
            default_params.update(params)
        super().__init__(name, default_params)

    def generate_signal(self, df: pd.DataFrame) -> str:
        if len(df) < self.params['slow_period']:
            return 'HOLD'

        fast_sma = df['close'].rolling(window=self.params['fast_period']).mean()
        slow_sma = df['close'].rolling(window=self.params['slow_period']).mean()

        if fast_sma.iloc[-2] <= slow_sma.iloc[-2] and fast_sma.iloc[-1] > slow_sma.iloc[-1]:
            return 'BUY'
        elif fast_sma.iloc[-2] >= slow_sma.iloc[-2] and fast_sma.iloc[-1] < slow_sma.iloc[-1]:
            return 'SELL'
            
        return 'HOLD'
