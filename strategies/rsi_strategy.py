import pandas as pd
from app.strategy.base_strategy import BaseStrategy

class RsiStrategy(BaseStrategy):
    """
    RSI Overbought/Oversold Strategy.
    """
    name = "RSI_Swing"
    
    def __init__(self, name="RSI_Swing", params=None):
        default_params = {'period': 14, 'oversold': 30, 'overbought': 70}
        if params:
            default_params.update(params)
        super().__init__(name, default_params)

    def generate_signal(self, df: pd.DataFrame) -> str:
        if len(df) < self.params['period'] + 1:
            return 'HOLD'

        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.params['period']).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params['period']).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        # Buy when crossing UP from oversold
        if prev_rsi <= self.params['oversold'] and current_rsi > self.params['oversold']:
            return 'BUY'
        # Sell when crossing DOWN from overbought
        elif prev_rsi >= self.params['overbought'] and current_rsi < self.params['overbought']:
            return 'SELL'
            
        return 'HOLD'
