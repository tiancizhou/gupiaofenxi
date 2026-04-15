# A股智能分析助手

一个自用的 Web 端股票分析助手。

- 后端：`FastAPI`
- 数据：`akshare`
- 模型：
  - `GLM` 走 `Anthropic Messages`
  - `gpt-5.4` 当前也走 `Anthropic Messages`

## 本地开发

推荐使用 `uv`。

### Windows 开发

直接使用 PowerShell：

```powershell
./scripts/dev.ps1
```

运行测试：

```powershell
./scripts/test.ps1
```

如果你不想用脚本，也可以直接运行：

```powershell
uv sync --dev
uv run python run.py
uv run pytest -v
```

### 1. 安装依赖

```bash
uv sync --dev
```

### 2. 配置环境变量

创建 `.env`，至少配置一组模型：

```env
LLM_OPENAI_API_KEY=your-key
LLM_OPENAI_BASE_URL=http://your-anthropic-compatible-endpoint
LLM_OPENAI_MODEL=gpt-5.4

LLM_GLM_API_KEY=your-glm-key
LLM_GLM_BASE_URL=https://open.bigmodel.cn/api/anthropic
LLM_GLM_MODEL=glm-5.1

CONV_MAX_MESSAGES=50
CONV_TTL_SECONDS=3600
CONV_MAX_CONVERSATIONS=1000
```

### 3. 启动服务

```bash
uv run python run.py
```

或者：

```bash
make run
```

默认监听：`127.0.0.1:8000`

浏览器访问：`http://127.0.0.1:8000`

### 4. 运行测试

```bash
uv run pytest -v
```

或者：

```bash
make test
```

## macOS 部署建议

在 Mac Mini 上：

```bash
uv sync --dev
uv run python run.py
```

也可以直接：

```bash
make install
make run
```

如果你要配合 `cloudflared` 或其他内网穿透，当前服务默认监听 `127.0.0.1:8000`。

### macOS 部署前检查清单

1. 安装 `uv`

```bash
uv --version
```

2. 确认 Python 版本不低于 `3.11`

```bash
uv run python --version
```

3. 准备 `.env`

要求：
- `LLM_GLM_BASE_URL` 使用 `Anthropic Messages` 地址
- `LLM_OPENAI_BASE_URL` 如果你的 `gpt-5.4` 中转站走 `Anthropic Messages`，不要带 `/v1`
- 填好 `CONV_*` 会话存储参数

4. 安装依赖

```bash
uv sync --dev
```

5. 跑测试

```bash
uv run pytest -v
```

6. 本地启动验证

```bash
uv run python run.py
```

检查：
- `http://127.0.0.1:8000` 能打开
- 模型列表能显示 `glm` 和 `openai`
- `glm` 能调用工具
- `gpt-5.4` 能流式返回

7. 如果部署到公网穿透

检查：
- 穿透服务转发到 `127.0.0.1:8000`
- macOS 防火墙和代理规则不要拦截本机回环访问
- `.env` 没有被提交到 git

## 当前说明

- `glm` 和 `gpt-5.4` 当前都走 `Anthropic Messages`
- 前端支持多会话后台生成、停止生成、删除会话、调试面板、阶段状态和耗时显示
- `screen_stocks` 已接入项目内的 Python 选股逻辑
- `get_stock_price` 已增加备用数据源 fallback
