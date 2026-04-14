import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, delete, desc
from ..storage.database import OHLCVCache, SessionLocal

class CacheManager:
    """
    Handles persistence of OHLCV data in the local SQLite database.
    """
    def __init__(self, db_session: Session = None):
        # We allow passing a session or it will create its own
        self.db = db_session if db_session else SessionLocal()

    def load_ohlcv(self, symbol: str, timeframe: str, limit: int = 2000) -> pd.DataFrame:
        """
        Loads OHLCV data from the local database.
        """
        query = self.db.query(OHLCVCache).filter(
            and_(
                OHLCVCache.symbol == symbol,
                OHLCVCache.timeframe == timeframe
            )
        ).order_by(desc(OHLCVCache.timestamp)).limit(limit)
        
        objects = query.all()
        if not objects:
            return pd.DataFrame()

        # Convert to list of dicts then to DataFrame
        data = [{
            'timestamp': obj.timestamp,
            'open': obj.open,
            'high': obj.high,
            'low': obj.low,
            'close': obj.close,
            'volume': obj.volume
        } for obj in reversed(objects)] # Reverse to get oldest first
        
        return pd.DataFrame(data)

    def save_ohlcv(self, df: pd.DataFrame, symbol: str, timeframe: str, source: str):
        """
        Saves OHLCV data to the local database, avoiding duplicates.
        """
        if df.empty:
            return

        for _, row in df.iterrows():
            ts = row['timestamp']
            # Check if this bar already exists
            existing = self.db.query(OHLCVCache).filter(
                and_(
                    OHLCVCache.symbol == symbol,
                    OHLCVCache.timeframe == timeframe,
                    OHLCVCache.timestamp == ts
                )
            ).first()
            
            if existing:
                existing.open = row['open']
                existing.high = row['high']
                existing.low = row['low']
                existing.close = row['close']
                existing.volume = row['volume']
            else:
                new_bar = OHLCVCache(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume'],
                    source=source
                )
                self.db.add(new_bar)
        
        self.db.commit()

    def cleanup(self, symbol: str, timeframe: str, max_rows: int = 2000):
        """
        Delete older rows if the count exceeds the limit for a specific symbol/timeframe.
        """
        # Count current rows
        count = self.db.query(OHLCVCache).filter(
            and_(OHLCVCache.symbol == symbol, OHLCVCache.timeframe == timeframe)
        ).count()
        
        if count > max_rows:
            # Find the timestamp of the bar that marks the 'max_rows' newest ones
            cutoff_row = self.db.query(OHLCVCache).filter(
                and_(OHLCVCache.symbol == symbol, OHLCVCache.timeframe == timeframe)
            ).order_by(desc(OHLCVCache.timestamp)).offset(max_rows).first()
            
            if cutoff_row:
                # Delete anything older or equal to this cutoff
                self.db.execute(
                    delete(OHLCVCache).where(
                        and_(
                            OHLCVCache.symbol == symbol,
                            OHLCVCache.timeframe == timeframe,
                            OHLCVCache.timestamp <= cutoff_row.timestamp
                        )
                    )
                )
                self.db.commit()

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
