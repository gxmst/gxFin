# 🏮 gxFin

gxFin 是一个专为个人量化交易者设计的**轻量级虚拟复盘与模拟交易执行系统**。它的核心定位并不是“重型回测平台”，而是一个**低能耗（内存占用通常 < 300MB）**、可部署在廉价 VPS 上 24/7 运行的**实盘模拟检验器**。

通过严格的 **Next-Bar-Open** 延迟执行语义与 0.2% 滑点手续费引擎，gxFin 可以帮助您在将策略接入真金白银的实盘 API 前，做最后的长时间“脱水检验”。

---

## 🎯 核心特性

- **严格的执行语义**：彻底杜绝“偷看未来”的回测偏误。无论是 Web 快速回测还是 24/7 Runner，所有的模拟订单一律在信号 K 线闭合后的**下一根 K 线开盘价 (Next Bar Open)** 执行。
- **抗封锁行情缓存**：针对币安 (CCXT) 和美股 (yfinance) 构建了双重获取方案，所有历史 K 线和最新 Ticker 都会无缝存入本地 SQLite。有效降低由于高频网络请求引起的交易所 IP 封禁 (Rate-Limiting)。
- **美股交易日完美对齐**：使用 `pytz` 精确抛弃生硬的 UTC 分割，所有的美股 4h 等中长周期 K 线均牢牢锚定美东时区的开盘 (09:30 EST) 进行时段重组。
- **解耦的架构**：后台 `Runner` 与前台 `Streamlit` 界面相互独立。通过基于 `WAL` 模式的 SQLite 进行消息轮询与状态同步。前台即使崩溃，后台的止损与盯盘依然照常运转。
- **模块化策略热播插拔**：所有的量化策略仅需编写为单个 `.py` 文件放入 `strategies/` 目录。系统会动态识别并供 Web 端一键切换。内置 AST 代码扫描以拦截最基础的输入风险。

---

## 🏗️ 基础系统架构

```text
gxFin/
├── app/
│   ├── broker/          # 虚拟撮合引擎 (管理余额/订单、模拟成交滑点)
│   ├── data/            # 行情调度层 (Binance/Stock Provider + Cache Manager 缓存维护)
│   ├── runtime/         # 核心运行时 (24/7 永远在线守护进程, Runner)
│   ├── storage/         # 数据库ORM抽象 (系统状态、资金流、配置同步)
│   ├── strategy/        # 策略计算层 (含 AST Sandbox、动态加载器、轻量回测器)
│   └── ui/              # Web 客户端 (Streamlit 控制台、密码拦截与图表绘制)
├── data/                # [运行生成] 本地数据库 gxfin.db 与运行时日志
├── strategies/          # 策略仓库，存放用户自定义的策略 .py 文件
├── .env.example         # 环境变量模板
└── pyproject.toml       # 依赖配单
```

---

## 🚀 安装部署指南 (VPS)

gxFin 推荐在 Python 3.9+ 的 Linux VPS 上运行。

#### 1. 初始化项目与依赖
```bash
git clone https://github.com/gxmst/gxFin.git
cd gxFin

# 安装项目本体及依赖 (可使用 pip 或 uv)
pip install -e .
```

#### 2. 配置环境变量
系统具备自我保护设定，由于未强制沙箱化，所有未经审计的策略执行拥有等同于系统权限。因此必须配置独立密码以防止公网 RCE 劫持。
```bash
cp .env.example .env
nano .env # 必须修改 ADMIN_PASSWORD 的值，不能使用默认的 gxfin123
```

#### 3. 启动后台引擎 (Runner)
让核心盯盘引擎在后台持久运行。
```bash
nohup python -m app.runtime.runner > data/runner_stdout.log 2>&1 &
```

#### 4. 启动控制台界面 (UI)
启动 Web UI。系统默认将在 `8501` 端口开启面板。
```bash
streamlit run app/ui/main.py
```
> **提示**：如果部署在公网，推荐使用 Nginx 等工具为 8501 端口配置反向代理和 HTTPS，以保障数据安全。

---

## 📝 编写你的第一个策略

所有的策略都需要继承 `app.strategy.base_strategy.BaseStrategy` 并实现 `generate_signal`。参考库内的 `sma_cross.py` 与 `rsi_strategy.py`。

> **⚠️ 重要的安全警告**
> gxFin 并没有内置 Docker 或内核级别的强制隔离环境。尽管框架包含了基础的 AST 防挂马拦截。但在生产环境的界面中，请**严格拒绝**任何来源不明的策略脚本，以免发生严重的数据与服务器资产损失！
