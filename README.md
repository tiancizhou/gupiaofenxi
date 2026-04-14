# A股智能分析助手

一个自用的 Web 端股票分析助手。

- 后端：`FastAPI`
- 数据：`akshare`
- 模型：
  - `GLM` 走 `Anthropic Messages`
  - `OpenAI Compatible` 走 `OpenAI 兼容协议`

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
LLM_OPENAI_BASE_URL=http://your-openai-compatible-endpoint/v1
LLM_OPENAI_MODEL=gpt-5.4

LLM_GLM_API_KEY=your-glm-key
LLM_GLM_BASE_URL=https://open.bigmodel.cn/api/anthropic
LLM_GLM_MODEL=glm-5.1
```

### 3. 启动服务

```bash
uv run python run.py
```

或者：

```bash
make run
```

默认监听：`0.0.0.0:8000`

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

如果你要配合 `cloudflared` 或其他内网穿透，保持服务监听 `0.0.0.0:8000` 即可。

## 当前说明

- `openai` 协议路径支持 SSE 流式输出
- `glm` 的 Anthropic Messages 路径当前先走非流式收口后返回
- `screen_stocks` 已接入项目内的 Python 选股逻辑
