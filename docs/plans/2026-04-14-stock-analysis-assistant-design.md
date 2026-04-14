# A股智能分析助手 — 设计文档

## 目标

构建一个自用的 Web 端 A 股交互式分析助手。用户通过类似 ChatGPT 的对话界面提问，后端调用大模型（支持 GLM 和 OpenAI 兼容中转站模型），模型通过 Tool Use 自主调用行情/财务/新闻等数据接口，生成综合分析回复。

## 用户场景

- 部署在 Mac Mini，通过 Cloudflare 内网穿透远程访问
- 使用者仅自己一人
- 支持手机浏览器访问

## 架构

```
浏览器 <--SSE--> FastAPI (Python)
                      |
          +-----------+-----------+
          |           |           |
     LLM API      akshare    screen.py
  (GLM/OpenAI)  (行情数据)  (选股逻辑)
```

## 技术栈

- **后端**: Python 3.11+ / FastAPI / uvicorn
- **数据源**: akshare（替代 mcporter + aktools MCP，去掉中间层）
- **LLM**: OpenAI 兼容 API，支持多 provider 切换
- **前端**: 单 HTML 文件，Tailwind CSS CDN，原生 JS，SSE 流式接收
- **配置**: `.env` 文件 + python-dotenv

## 项目结构

```
gupiaofenxi/
├── server.py              # FastAPI 入口，SSE 流式对话端点
├── llm.py                 # OpenAI 兼容 API 调用 + Tool Use 循环
├── tools.py               # 注册给 LLM 的工具函数定义和实现
├── config.py              # 配置加载（多 provider）
├── static/
│   └── index.html         # 单页面对话 UI
├── skills/                # 现有 skill 文件（保留参考）
├── docs/plans/            # 设计文档
├── requirements.txt
└── .env                   # API Key 等敏感配置（不提交 git）
```

## 核心模块设计

### 1. LLM 调用 (llm.py)

- 使用 `openai` Python SDK（兼容所有 OpenAI 协议的 provider）
- 支持 Tool Use：将工具定义传入 `tools` 参数，处理 `tool_calls` 响应
- 多轮工具调用循环：LLM 可连续调用多个工具后再生成最终回复
- 流式输出：SSE 逐 token 推送到前端

### 2. 工具定义 (tools.py)

注册以下工具供 LLM 自主调用：

| 工具名 | 功能 | akshare 接口 |
|--------|------|-------------|
| `get_stock_price` | 查股票行情/K线 | `stock_zh_a_hist` |
| `get_stock_info` | 查股票基本信息 | `stock_individual_info_em` |
| `get_financial_indicators` | 财务指标 | `stock_financial_abstract_ths` |
| `get_stock_news` | 个股新闻 | `stock_news_em` |
| `get_market_sentiment` | 涨停池/龙虎榜/资金流 | `stock_zt_pool_em` / `stock_lhb_ggtj_sina` / `stock_sector_fund_flow_rank` |
| `get_global_news` | 全球财经新闻 | `news_cctv_date` |
| `screen_stocks` | 条件选股 | 内嵌 screen.py 逻辑 |

每个工具函数返回结构化 JSON，LLM 据此生成分析。

### 3. 服务端 (server.py)

- `GET /` — 返回 static/index.html
- `POST /chat` — 接收 `{message, conversation_id, model}`, 返回 SSE 流
- `GET /models` — 返回可用模型列表
- 对话历史存储在内存中（单用户场景足够）

### 4. 前端界面 (static/index.html)

- 仿 ChatGPT 布局：
  - 左侧栏：历史对话列表 + 新建对话按钮 + 模型选择下拉框
  - 右侧：对话区域
- 对话气泡：用户消息靠右，AI 回复靠左（Markdown 渲染，用 marked.js）
- 工具调用状态：AI 调用工具时显示"正在查询行情..."等提示
- 响应式设计，移动端适配
- 历史对话存储在 localStorage

### 5. 配置 (config.py / .env)

```env
# Provider 1: GLM
LLM_GLM_API_KEY=xxx
LLM_GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_GLM_MODEL=glm-4-plus

# Provider 2: OpenAI 兼容中转站
LLM_OPENAI_API_KEY=sk-xxx
LLM_OPENAI_BASE_URL=https://api.siliconflow.cn/v1
LLM_OPENAI_MODEL=deepseek-ai/DeepSeek-V3
```

## 数据流

```
1. 用户输入: "帮我分析一下贵州茅台最近走势"
2. 前端 POST /chat → 后端
3. LLM 判断需要调工具 → 返回 tool_calls: [get_stock_price(600519)]
4. 后端执行工具，akshare 拉取数据 → 结果回传 LLM
5. LLM 可能再调: get_financial_indicators(600519)
6. 后端执行 → 结果回传 LLM
7. LLM 生成最终分析回复 → SSE 流式推送到前端
8. 前端实时渲染 Markdown
```

## 系统提示词

LLM 系统提示词将包含：
- 角色定义：A股专业分析师
- A股市场规则（sh/sz 代码规则、交易时间等）
- 工具使用指引（何时调哪个工具）
- 回复风格：中文、结构化、关键数据加粗

## 错误处理

- akshare 调用失败：返回错误信息给 LLM，让 LLM 告知用户数据暂时不可用
- LLM API 调用失败：前端显示错误提示
- 网络超时：设置合理的超时时间（行情接口 10s，LLM 60s）

## 非目标（YAGNI）

- 用户认证/登录（自用无需）
- 数据库（内存 + localStorage 足够）
- 实时行情推送（对话式按需查询即可）
- 交易功能
- 复杂仪表盘/图表
