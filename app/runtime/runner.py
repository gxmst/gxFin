import os
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
import pandas as pd

from sqlalchemy.orm import Session
from ..storage.database import SessionLocal, init_db, SystemCommand, AppStatus, AccountState
from ..data.binance_provider import BinanceProvider
from ..data.stock_provider import StockProvider
from ..broker.mock_broker import MockBroker
from ..strategy.strategy_loader import StrategyLoader

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging setup to file
LOG_DIR = os.path.join(os.getcwd(), 'data')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
LOG_FILE = os.path.join(LOG_DIR, 'gxfin.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("gxFin.Runner")

class TradingRunner:
    def __init__(self):
        init_db()
        self.db: Session = SessionLocal()
        self.binance = BinanceProvider()
        self.stock = StockProvider()
        
        # Load pessimism factor from env
        pessimism = float(os.getenv("PESSIMISM_FACTOR", 0.002))
        self.broker = MockBroker(self.db, pessimism_factor=pessimism)
        
        self.strategy_loader = StrategyLoader()
        self.is_running = False
        self.current_strategy = None
        self.symbol = "BTC/USDT"
        self.timeframe = "1h"

    def run(self):
        logger.info("Runner starting...")
        while True:
            try:
                self.process_commands()
                self.update_status()

                if self.is_running:
                    self.execute_tick()
                
                # Check every 10 seconds for commands or next tick
                time.sleep(10)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(10)

    def process_commands(self):
        cmd = self.db.query(SystemCommand).filter(SystemCommand.status == 'PENDING').first()
        if not cmd:
            return

        logger.info(f"Processing command: {cmd.command}")
        if cmd.command == 'START':
            params = cmd.params or {}
            strat_name = params.get('strategy', 'SMA_Cross')
            strat_class = self.strategy_loader.get_strategy_class(strat_name)
            
            if strat_class:
                self.current_strategy = strat_class()
                self.is_running = True
                self.symbol = params.get('symbol', self.symbol)
                self.timeframe = params.get('timeframe', self.timeframe)
                logger.info(f"Started strategy: {strat_name} on {self.symbol}")
            else:
                logger.error(f"Strategy {strat_name} not found!")
                cmd.status = 'FAILED'
                return

        elif cmd.command == 'STOP':
            self.is_running = False
        elif cmd.command == 'SWITCH_STRATEGY':
            # For MVP, we just reset the running state and maybe close positions
            # according to the "pessimistic" rule
            self.broker.execute_order('SELL', self.symbol, self.get_last_price(), "SYSTEM_SWITCH")
            
            params = cmd.params or {}
            strat_name = params.get('strategy', 'SMA_Cross')
            strat_class = self.strategy_loader.get_strategy_class(strat_name)
            
            if strat_class:
                self.current_strategy = strat_class()
                self.is_running = True
                self.symbol = params.get('symbol', self.symbol)
                self.timeframe = params.get('timeframe', self.timeframe)
                logger.info(f"Switched to strategy: {strat_name}")
            else:
                logger.error(f"Strategy {strat_name} not found during switch!")
                cmd.status = 'FAILED'
                return

        cmd.status = 'EXECUTED'
        self.db.commit()

    def update_status(self):
        status = self.db.query(AppStatus).first()
        if status:
            status.is_running = self.is_running
            status.current_strategy = self.current_strategy.name if self.current_strategy else "None"
            status.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            # Sync pessimism factor from UI
            if status.pessimism_factor is not None and self.broker.pessimism_factor != status.pessimism_factor:
                self.broker.pessimism_factor = status.pessimism_factor
                logger.info(f"Updated pessimism factor to {status.pessimism_factor}")
            
            self.db.commit()

    def execute_tick(self):
        # Determine provider
        provider = self.binance if '/' in self.symbol else self.stock
        
        # Fetch data with cache
        df = provider.fetch_ohlcv_with_cache(self.symbol, self.timeframe, limit=100)
        if df.empty:
            logger.warning(f"No data for {self.symbol}")
            return

        # Ensure we only use fully closed bars
        # Add a 5-second buffer to allow exchanges to finalize their candles
        duration = self._get_timeframe_delta(self.timeframe)
        buffer_time = pd.Timedelta(seconds=5)
        last_bar_time = df.iloc[-1]['timestamp']
        current_time = datetime.now(timezone.utc)
        
        # If the current time hasn't passed the bar's hypothetical close time + buffer, it's incomplete
        if current_time < (last_bar_time + duration + buffer_time):
            if len(df) > 1:
                df = df.iloc[:-1]
            else:
                return # Only forming bar available, wait

        last_closed_time = df.iloc[-1]['timestamp']
        status = self.db.query(AppStatus).first()
        if status.last_tick_time == last_closed_time:
            return  # We already processed this closed bar

        logger.info(f"Executing tick for {self.symbol} at {last_closed_time}")

        
        signal = self.current_strategy.generate_signal(df)
        if signal in ['BUY', 'SELL']:
            # Use the VERY LATEST price (next bar open) for execution
            execution_price = self.get_last_price()
            if execution_price > 0:
                self.broker.execute_order(signal, self.symbol, execution_price, self.current_strategy.name)
            else:
                logger.error("Failed to get live execution price.")

        status.last_tick_time = last_closed_time
        self.db.commit()

    def get_last_price(self):
        # Helper for real-time execution price
        provider = self.binance if '/' in self.symbol else self.stock
        try:
            return provider.fetch_ticker(self.symbol)
        except Exception as e:
            logger.error(f"Error fetching real-time price: {e}")
            # Fallback to last cache close if ticker fails
            df = provider.fetch_ohlcv_with_cache(self.symbol, self.timeframe, limit=1)
            return df.iloc[-1]['close'] if not df.empty else 0

    def _get_timeframe_delta(self, timeframe: str) -> pd.Timedelta:
        mapping = {
            '1m': pd.Timedelta(minutes=1),
            '5m': pd.Timedelta(minutes=5),
            '15m': pd.Timedelta(minutes=15),
            '30m': pd.Timedelta(minutes=30),
            '1h': pd.Timedelta(hours=1),
            '4h': pd.Timedelta(hours=4),
            '1d': pd.Timedelta(days=1)
        }
        return mapping.get(timeframe, pd.Timedelta(hours=1))

if __name__ == "__main__":
    runner = TradingRunner()
    runner.run()
