from app.data.binance_provider import BinanceProvider
from app.data.stock_provider import StockProvider
import pandas as pd

def test_binance():
    print("Testing Binance Data Fetching...")
    provider = BinanceProvider()
    df = provider.fetch_ohlcv("BTC/USDT", "1h", limit=5)
    print(df)
    assert not df.empty
    print("Binance OK\n")

def test_stocks():
    print("Testing US Stock Data Fetching...")
    provider = StockProvider()
    df = provider.fetch_ohlcv("AAPL", "1d", limit=5)
    print(df)
    assert not df.empty
    print("Stocks OK\n")

if __name__ == "__main__":
    try:
        test_binance()
        test_stocks()
        print("ALL DATA PROVIDERS WORKING CORRECTLY.")
    except Exception as e:
        print(f"FAILED: {e}")
