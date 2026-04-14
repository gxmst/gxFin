import ccxt
import pandas as pd
from typing import Optional, List
from .base_provider import BaseDataProvider
from datetime import datetime

class BinanceProvider(BaseDataProvider):
    """
    Data provider for Binance Futures Markets using CCXT.
    Does NOT require API keys for public data.
    """
    
    def __init__(self):
        self.source_name = 'binance'
        super().__init__()
        self.exchange = ccxt.binance({
            'options': {
                'defaultType': 'future',  # Use USD-M Futures by default
            },
            'enableRateLimit': True,
        })

    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = '1h', 
        since: Optional[int] = None, 
        limit: Optional[int] = 100
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Binance Futures.
        """
        if '/' not in symbol:
            symbol = f"{symbol}/USDT"
            
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since, limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        return df

    def fetch_ticker(self, symbol: str) -> float:
        """Fetch the current last price for a symbol."""
        if '/' not in symbol:
            symbol = f"{symbol}/USDT"
        ticker = self.exchange.fetch_ticker(symbol)
        return float(ticker['last'])

    def get_available_symbols(self) -> List[str]:
        """
        Return a list of popular Binance Futures pairs.
        """
        return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'ORDI/USDT']
