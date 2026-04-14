from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, List
from .cache_manager import CacheManager

class BaseDataProvider(ABC):
    """
    Abstract base class for all data providers.
    Ensures a consistent interface for fetching market data.
    """
    
    def __init__(self):
        self.cache = CacheManager()

    @abstractmethod
    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str, 
        since: Optional[int] = None, 
        limit: Optional[int] = 100
    ) -> pd.DataFrame:
        pass

    def fetch_ohlcv_with_cache(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """
        Attempt to load from cache first. 
        If not enough data, fetch from remote and update cache.
        """
        df_cached = self.cache.load_ohlcv(symbol, timeframe, limit=limit)
        # Determine how much to fetch from remote
        # If cache lacks the requested limit, fetch the full limit. Otherwise fetch 5 to update the latest bars.
        fetch_limit = limit if df_cached.empty or len(df_cached) < limit else 5
        
        df_remote = self.fetch_ohlcv(symbol, timeframe, limit=fetch_limit)
        if not df_remote.empty:
            source = getattr(self, 'source_name', 'unknown')
            self.cache.save_ohlcv(df_remote, symbol, timeframe, source)
            # Run cleanup occasionally
            self.cache.cleanup(symbol, timeframe)
            
            # Reload cache to return the newly merged data
            df_cached = self.cache.load_ohlcv(symbol, timeframe, limit=limit)
            
        return df_cached

    @abstractmethod
    def fetch_ticker(self, symbol: str) -> float:
        """Fetch the current real-time price for the symbol."""
        pass

    @abstractmethod
    def get_available_symbols(self) -> List[str]:
        """Return a list of common tradable symbols for this provider."""
        pass
