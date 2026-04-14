import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, JSON, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event

Base = declarative_base()

class OHLCVCache(Base):
    __tablename__ = 'ohlcv_cache'
    id = Column(Integer, primary_key=True)
    symbol = Column(String(50), index=True)
    timeframe = Column(String(10), index=True)
    timestamp = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    source = Column(String(50))

class TradeHistory(Base):
    __tablename__ = 'trade_history'
    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(100))
    symbol = Column(String(50))
    action = Column(String(10))  # BUY, SELL
    price = Column(Float)
    qty = Column(Float)
    commission = Column(Float)
    slippage = Column(Float)
    total_cost = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class AccountState(Base):
    __tablename__ = 'account_state'
    id = Column(Integer, primary_key=True)
    balance = Column(Float, default=100000.0)
    position_qty = Column(Float, default=0.0)
    position_avg_price = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

class SystemCommand(Base):
    __tablename__ = 'system_commands'
    id = Column(Integer, primary_key=True)
    # START_STRATEGY, STOP_STRATEGY, SWITCH_STRATEGY
    command = Column(String(50))
    params = Column(JSON)
    status = Column(String(20), default='PENDING')  # PENDING, EXECUTED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow)

class AppStatus(Base):
    __tablename__ = 'app_status'
    id = Column(Integer, primary_key=True)
    current_strategy = Column(String(100))
    is_running = Column(Boolean, default=False)
    pessimism_factor = Column(Float, default=0.002)
    last_tick_time = Column(DateTime)
    last_error = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Database Engine Setup
DB_PATH = os.path.join(os.getcwd(), 'data', 'gxfin.db')
engine = create_engine(
    f'sqlite:///{DB_PATH}', 
    connect_args={"check_same_thread": False, "timeout": 20}
)

# Enable WAL mode for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    if not os.path.exists(os.path.dirname(DB_PATH)):
        os.makedirs(os.path.dirname(DB_PATH))
    Base.metadata.create_all(bind=engine)
    
    # Initialize default account state if not exists
    db = SessionLocal()
    if db.query(AccountState).count() == 0:
        initial_balance = float(os.getenv("INITIAL_BALANCE", 100000.0))
        initial_account = AccountState(balance=initial_balance)
        db.add(initial_account)
    if db.query(AppStatus).count() == 0:
        initial_status = AppStatus(is_running=False, pessimism_factor=0.002)
        db.add(initial_status)
    db.commit()

    # DB Migration: Inject pessimism_factor if it doesn't exist
    from sqlalchemy import text
    try:
        db.execute(text("SELECT pessimism_factor FROM app_status LIMIT 1"))
    except Exception:
        db.rollback()
        db.execute(text("ALTER TABLE app_status ADD COLUMN pessimism_factor FLOAT DEFAULT 0.002"))
        db.commit()

    db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
