import pandas as pd
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    """
    Base class for all trading strategies.
    Any strategy added to the strategies/ folder must inherit from this class.
    """
    
    def __init__(self, name: str, params: dict = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> str:
        """
        Receives a DataFrame of OHLCV data.
        Returns: 'BUY', 'SELL', or 'HOLD'.
        """
        pass
