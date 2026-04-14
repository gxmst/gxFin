# gxFin

gxFin 是一个面向单用户的轻量量化模拟执行工具。

它的重点不是做完整交易平台，而是提供一个比较克制的闭环：

- 在线获取行情
- 加载本地策略文件
- 在 VPS 或本地按周期运行单策略
- 用虚拟账户模拟买卖
- 通过简单 Web UI 查看状态、日志和轻量回测结果

## 项目定位

适合：

- 个人兴趣项目
- 单用户使用
- 低频策略验证
- 上线前的虚拟盘观察

不适合：

- 高频交易
- 多用户协作
- 多策略并发管理
- 真实下单
- 把策略文件当作安全沙箱执行

## 当前能力

- 币安期货行情读取，基于 `ccxt`
- 美股 / ETF 数据读取，基于 `yfinance`
- 单策略 Runner 常驻执行
- 本地 SQLite 缓存、交易记录和状态存储
- Streamlit 管理页面
- 轻量历史回测
- 简单密码保护

## 执行语义

项目当前采用一套偏保守的模拟执行思路：

- 策略信号基于已闭合 K 线计算
- Runner 会尽量避免使用尚未闭合的 bar
- 模拟成交会加入统一的摩擦成本

需要注意：

- 回测与实时执行都在尽量减少 look-ahead bias
- 但实时执行使用的是信号确认后的实时价格近似，而不是交易所真实成交回报
- 因此它更适合做“策略观察”和“风险预演”，而不是严格意义上的成交复现

## 目录结构

```text
gxFin/
├── app/
│   ├── broker/
│   ├── data/
│   ├── runtime/
│   ├── storage/
│   ├── strategy/
│   └── ui/
├── strategies/
├── data/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
```

或：

```bash
uv sync
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

至少要修改：

- `ADMIN_PASSWORD`

可选配置：

- `PESSIMISM_FACTOR`

### 3. 启动 Runner

```bash
uv run python -m app.runtime.runner
```

### 4. 启动 UI

默认访问端口为 `8501`。

```bash
uv run streamlit run app/ui/main.py
```

## 策略开发

策略以单独的 Python 文件存在于 `strategies/` 目录。

内置示例：

- `strategies/sma_cross.py`
- `strategies/rsi_strategy.py`

策略需要继承 `BaseStrategy` 并实现 `generate_signal(df)`，返回：

- `BUY`
- `SELL`
- `HOLD`

## 安全说明

这个项目**不提供真正的策略沙箱**。

仓库中的 AST 检查更接近“静态风格审查”，只能拦截一部分明显危险的写法，不能替代操作系统层面的隔离。

因此：

- 不要运行来源不明的策略文件
- 如果部署到公网，建议放在 Docker 和反向代理后面
- UI 的密码保护只能算基础保护，不是完整安全方案

## 部署建议

更适合的部署方式：

- 单台轻量 VPS
- Docker 或本地 Python 环境
- 低频轮询
- 少量标的
- 单策略运行

如果后续要继续扩展，建议优先补：

- 更明确的集成测试
- 更一致的回测 / 实时成交模型说明
- 更清晰的故障恢复和状态记录
