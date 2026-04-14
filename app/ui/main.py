import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from app.storage.database import SessionLocal, init_db, AccountState, TradeHistory, AppStatus, SystemCommand
from app.data.binance_provider import BinanceProvider
from app.data.stock_provider import StockProvider
from app.strategy.strategy_loader import StrategyLoader
from app.strategy.backtester import LightBacktester
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "gxfin123")
LOG_DIR = os.path.join(os.getcwd(), 'data')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
LOG_FILE = os.path.join(LOG_DIR, 'gxfin.log')

# Setup UI Logging to shared file
ui_logger = logging.getLogger("gxFin.UI")
if not ui_logger.handlers:
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    ui_logger.addHandler(fh)
    ui_logger.setLevel(logging.INFO)

# Page Config
st.set_page_config(page_title="gxFin - 个人量化中心", layout="wide", initial_sidebar_state="expanded")

# --- Authentication ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 gxFin 登录")
    
    # Force default password change
    if ADMIN_PASSWORD == "gxfin123":
        st.error("❌ 检测到默认密码！为了您的 VPS 安全，请先在根目录的 `.env` 文件中修改 `ADMIN_PASSWORD`。")
        st.info("系统当前处于锁定状态，修改并重启后方可登录。")
        st.stop()

    password = st.text_input("请输入管理员密码", type="password")
    if st.button("进入系统"):
        if password == ADMIN_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("密码错误")
    st.stop()

# --- Initialize DB ---
if 'db' not in st.session_state:
    init_db()
    st.session_state.db = SessionLocal()

db = st.session_state.db
loader = StrategyLoader()
available_strategies = loader.list_strategies()

def get_account():
    return db.query(AccountState).order_by(AccountState.id.desc()).first()

def get_status():
    return db.query(AppStatus).first()

def send_command(cmd, params=None):
    new_cmd = SystemCommand(command=cmd, params=params)
    db.add(new_cmd)
    db.commit()
    ui_logger.info(f"UI sent command: {cmd} with params {params}")
    st.success(f"指令 {cmd} 已发送")

# --- Sidebar ---
st.sidebar.title("🏮 gxFin 控制面板")
status = get_status()
account = get_account()

st.sidebar.subheader("运行状态")
if status:
    run_color = "green" if status.is_running else "red"
    st.sidebar.markdown(f"状态: :[{'运行中' if status.is_running else '已停止'}]({run_color})")
    
    # Heartbeat check
    if status.updated_at:
        from datetime import timezone
        seconds_since_update = (datetime.now(timezone.utc).replace(tzinfo=None) - status.updated_at).total_seconds()
        if seconds_since_update > 60:
            st.sidebar.warning("⚠️ 引擎可能已离线")
    
    st.sidebar.text(f"当前策略: {status.current_strategy}")

st.sidebar.divider()
st.sidebar.subheader("🛡️ 安全提示")
st.sidebar.warning("本系统不支持沙箱环境隔离。策略文件具有系统层级访问权限，请勿运行任何未经审核的代码。")
st.sidebar.divider()
st.sidebar.subheader("调参设置")
current_pessimism = float(status.pessimism_factor) if getattr(status, 'pessimism_factor', None) is not None else 0.002
ui_pessimism = st.sidebar.slider("模拟滑点/手续费 (%)", 0.0, 1.0, current_pessimism * 100, 0.05, help="影响双向摩擦成本")
new_pessimism = ui_pessimism / 100.0
if abs(current_pessimism - new_pessimism) > 0.0001:
    status.pessimism_factor = new_pessimism
    db.commit()

st.sidebar.divider()
st.sidebar.subheader("核心执行配置")
strat_name = st.sidebar.selectbox("启用策略", available_strategies if available_strategies else ["无"])
symbol = st.sidebar.selectbox("交易标的", ["BTC/USDT", "ETH/USDT", "AAPL", "NVDA"], index=0)
timeframe = st.sidebar.selectbox("执行周期", ["15m", "1h", "4h", "1d"], index=1)

if st.sidebar.button("▶ 启动策略", use_container_width=True):
    send_command('START', {'strategy': strat_name, 'symbol': symbol, 'timeframe': timeframe})
if st.sidebar.button("⏹ 停止策略", use_container_width=True):
    send_command('STOP')
if st.sidebar.button("🔄 强制平仓并重置", use_container_width=True):
    send_command('SWITCH_STRATEGY', {'strategy': strat_name, 'symbol': symbol, 'timeframe': timeframe})

if st.sidebar.button("🚪 退出登录"):
    st.session_state["authenticated"] = False
    st.rerun()

# --- Main Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 实盘仪表盘", "🧪 轻量回测", "📋 系统日志"])

# --- Tab 1: Dashboard ---
with tab1:
    if account:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("账户余额", f"${account.balance:,.2f}")
        c2.metric("当前持仓", f"{account.position_qty:.4f}")
        c3.metric("持仓均价", f"${account.position_avg_price:,.2f}")
        c4.metric("已实现盈亏", f"${account.realized_pnl:,.2f}")

    st.subheader("实时行情图表")
    provider = BinanceProvider() if '/' in symbol else StockProvider()
    df_live = provider.fetch_ohlcv_with_cache(symbol, timeframe, limit=100)
    if not df_live.empty:
        fig = go.Figure(data=[go.Candlestick(x=df_live['timestamp'], open=df_live['open'], high=df_live['high'], low=df_live['low'], close=df_live['close'])])
        fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("最近交易记录")
    history = db.query(TradeHistory).order_by(TradeHistory.timestamp.desc()).limit(10).all()
    if history:
        st.table(pd.DataFrame([{ 
            "时间": h.timestamp.strftime('%H:%M:%S'), 
            "动作": h.action, 
            "价格": f"{h.price:.4f}", 
            "数量": f"{h.qty:.6f}"
        } for h in history]))

# --- Tab 2: Backtest ---
with tab2:
    st.header("快速回测验证 (最近 1000 根线)")
    bt_strat = st.selectbox("回测策略", available_strategies, key="bt_strat")
    bt_symbol = st.selectbox("回测标的", ["BTC/USDT", "ETH/USDT", "NVDA"], key="bt_symbol")
    bt_timeframe = st.selectbox("回测周期", ["15m", "1h", "4h", "1d"], index=1, key="bt_tf")
    
    if st.button("开始运行回测"):
        with st.spinner("数据拉取中..."):
            bt_provider = BinanceProvider() if '/' in bt_symbol else StockProvider()
            df_hist = bt_provider.fetch_ohlcv_with_cache(bt_symbol, bt_timeframe, limit=1000)
            
            if not df_hist.empty:
                init_balance = float(os.getenv("INITIAL_BALANCE", 100000.0))
                tester = LightBacktester(initial_balance=init_balance, pessimism_factor=current_pessimism)
                strat_class = loader.get_strategy_class(bt_strat)
                if strat_class:
                    strategy = strat_class()
                    results = tester.run(strategy, df_hist)
                    
                    # Show results (FIXED INDENTATION)
                    res1, res2, res3, res4 = st.columns(4)
                    res1.metric("总收益率", f"{results['total_return']*100:.2f}%")
                    res2.metric("胜率", f"{results['win_rate']*100:.2f}%")
                    res3.metric("最大回撤", f"{results['max_drawdown']*100:.2f}%")
                    res4.metric("交易次数", f"{results['trade_count']}")
                    
                    # Equity Curve
                    st.subheader("资金曲线")
                    fig_bt = go.Figure()
                    fig_bt.add_trace(go.Scatter(y=results['equity_curve'], mode='lines', name='权益'))
                    fig_bt.update_layout(height=300, template="plotly_dark")
                    st.plotly_chart(fig_bt, use_container_width=True)
                else:
                    st.error("无法加载选中的策略类")
            else:
                st.error("数据拉取失败，请检查网络或标的名")

# --- Tab 3: Logs ---
with tab3:
    st.header("系统实时日志 (最后 100 条)")
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_lines = lines[-100:]
            st.code("".join(last_lines), language="text")
    else:
        st.warning("暂无日志文件，请确保后台引擎已启动。")
    
    if st.button("刷新日志"):
        st.rerun()
