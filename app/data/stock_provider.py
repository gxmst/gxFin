import yfinance as yf
import pandas as pd
from typing import Optional, List
from .base_provider import BaseDataProvider
from datetime import datetime

class StockProvider(BaseDataProvider):
    """
    Data provider for US Stocks using yfinance.
    Note: Data may be delayed by ~15 minutes.
    """
    def __init__(self):
        self.source_name = 'yfinance'
        super().__init__()
    
    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = '1h', 
        since: Optional[int] = None, 
        limit: Optional[int] = 100
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Yahoo Finance.
        Mapping timeframes: '1h' -> '60m', '1d' -> '1d'
        """
        # yfinance timeframe mapping
        # Supported: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
        mapping = {
            '1m': '1m', '2m': '2m', '5m': '5m', '15m': '15m', '30m': '30m',
            '60m': '60m', '1h': '60m', '4h': '60m',  # yf doesn't have 4h, use 60m
            '1d': '1d', '1wk': '1wk', '1mo': '1mo'
        }
        yf_interval = mapping.get(timeframe, '60m')
        
        # Determine period based on limit and interval
        if yf_interval in ['1m']: period = '7d'
        elif yf_interval in ['2m', '5m', '15m', '30m', '60m', '90m', '1h']: period = '730d'
        else: period = 'max'

        # Download data
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=yf_interval)
        
        if df.empty:
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
        df = df.reset_index()
        df = df.rename(columns={
            'Datetime': 'timestamp', 'Date': 'timestamp', 
            'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
        })
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        
        # 4h Aggregation Logic
        if timeframe == '4h' and not df.empty:
            import pytz
            df = df.set_index('timestamp')
            df.index = df.index.tz_convert('US/Eastern')
            # Anchor resampling to 09:30:00 US/Eastern to match market open
            anchor = pd.Timestamp('2000-01-01 09:30:00', tz='US/Eastern')
            df = df.resample('4h', origin=anchor).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            df.index = df.index.tz_convert('UTC')
            df = df.reset_index()
        
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(limit)

    def fetch_ticker(self, symbol: str) -> float:
        """Fetch the current last price for a stock via fast_info."""
        ticker = yf.Ticker(symbol)
        try:
            return float(ticker.fast_info['lastPrice'])
        except:
            # Fallback to last history close if fast_info fails
            df = ticker.history(period='1d', interval='1m')
            return float(df.iloc[-1]['Close']) if not df.empty else 0.0

    def get_available_symbols(self) -> List[str]:
        """Popular US Stocks / ETFs."""
        return ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'QQQ', 'SPY']
