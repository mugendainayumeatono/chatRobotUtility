# Simple LLM Client

轻量级、模块化的大语言模型（LLM）测试与交互客户端，支持多种 LLM 服务后端，提供自动化交互测试套件以及会话日志持久化功能。

---

## 目录

- [功能特性](#功能特性)
- [目录结构](#目录结构)
- [安装依赖](#安装依赖)
- [使用说明](#使用说明)
  - [1. OpenAI 兼容客户端 (`openAI_client.py`)](#1-openai-兼容客户端-openai_clientpy)
  - [2. AnythingLLM 客户端 (`anything-llm_client.py`)](#2-anythingllm-客户端-anything-llm_clientpy)
  - [3. RAGFlow 客户端 (`ragflow_client.py`)](#3-ragflow-客户端-ragflow_clientpy)
  - [4. 测试套件与日志保存 (`test_suite.py`)](#4-测试套件与日志保存-test_suitepy)
- [运行示例](#运行示例)
  - [示例 1：命令行运行 OpenAI 兼容客户端](#示例-1命令行运行-openai-兼容客户端)
  - [示例 2：使用脚本文件快捷运行 (`run.sh`)](#示例-2使用脚本文件快捷运行-runsh)
  - [示例 3：Python 代码中调用并运行测试套件](#示例-3python-代码中调用并运行测试套件)
  - [示例 4：自定义测试用例](#示例-4自定义测试用例)
- [日志管理](#日志管理)
- [Git 忽略配置](#git-忽略配置)

---

## 功能特性

- **多后端支持**：
  - **OpenAI 兼容协议**：对接 vLLM、Ollama、LocalAI、DeepSeek、Gemini Proxy 等服务。
  - **AnythingLLM**：支持 Workspace 与 Thread 会话管理，自动解析 RAG 知识库检索来源（Reference Sources）。
  - **RAGFlow**：支持基于 RAGFlow 服务的知识库问答对接。
- **流式与非流式**：OpenAI 客户端支持 `--stream` 流式输出与完整响应解析。
- **多模态支持（文生图保存与图文输入）**：
  - 当要求模型画一幅画时，支持自动解析模型返回的图片数据（包括 `images` 扩展字段、多模态 `content` 数组、Markdown/Data URI 内嵌图片以及远程图片链接），自动识别图片格式（`.jpg`、`.png`、`.webp`、`.gif`、`.bmp`）并保存至本地 `logs/` 文件夹中。
  - 支持通过 `--image` (`-i`) 传入本地图片或远程图片 URL 进行多模态图文问答。
- **自动化测试套件**：内置多个预设测试集（通用问答、产品咨询、网络设备排障、连通性探测、多模态画图等）。
- **思维链过滤**：自动识别并截断 `</think>` 标签前的深度思考内容，输出干净的最终回答。
- **日志与图片持久化**：测试运行过程、交互日志及模型生成的图片均自动保存至 `logs/` 文件夹下，并带有时间戳命名。

---

## 目录结构

```text
chatRobotUtility/
├── base_client.py         # HTTP 基础客户端类与测试调度器 (HTTPClient)
├── openAI_client.py       # OpenAI 兼容 API 客户端 (支持流式/非流式及多模态收发)
├── anything-llm_client.py # AnythingLLM 专用客户端 (支持 RAG 知识库与会话上下文)
├── ragflow_client.py      # RAGFlow 专用客户端
├── deepDeekOverOpenAI.py  # 简易 OpenAI 基础调用示例
├── test_suite.py          # 预设测试用例库与聊天内容/图片持久化管理器 (ChatContent)
├── run.sh                 # 本地快捷启动命令脚本 (已被 .gitignore 忽略)
├── requirements.txt       # Python 项目依赖
├── logs/                  # 交互日志与生成图片输出目录 (已被 .gitignore 忽略)
└── README.md              # 项目使用说明文档
```

---

## 安装依赖

使用 `pip` 安装依赖：

```bash
pip install -r requirements.txt
```

或者使用 `uv` 虚拟环境与依赖管理工具：

```bash
uv pip install -r requirements.txt
```

---

## 使用说明

### 1. OpenAI 兼容客户端 (`openAI_client.py`)

支持通过命令行参数快速指定服务地址、模型名及密钥：

```bash
python openAI_client.py [参数]
```

#### 命令行参数说明

| 参数 | 缩写 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `--model` | | `str` | `default` | 模型名称 |
| `--url` | | `str` | `http://127.0.0.1:30000/v1` | OpenAI 兼容接口 Base URL |
| `--api_key` | | `str` | 环境变量 `OPENAI_API_KEY` 或 `EMPTY` | API 认证密钥 |
| `--stream` | | 标志 | `False` | 启用流式（Stream）输出模式 |
| `--test-suite` | `--test`, `-t` | `str` | `test_5_ping` | 指定执行的测试套件名称（如 `test_1`、`test_6_draw` 等） |
| `--prompt` | `-p` | `str` | `None` | 直接发送单条提示词（例如要求模型画一幅画），不指定则运行测试套件 |
| `--image`, `--attachment` | `-i`, `-a` | `list[str]` | `None` | 附加的本地文件路径列表（可指定多个） |
| `--list-test` | `--list-tests` | 标志 | `False` | 列出所有可用的测试套件并退出 |
| `--list-modes` | `--list-mode`, `--list-models` | 标志 | `False` | 列出服务端全部可用的模型列表并退出 |

---

### 2. AnythingLLM 客户端 (`anything-llm_client.py`)

用于连接 AnythingLLM 服务，支持工作区（Workspace）和线程（Thread）会话管理。

- **命令行参数**：支持 `--host`, `--port`, `--workspace`, `--mode` (`chat` 或 `query`), `--no_context`, `--test-suite` (`-t`), `--list-test`, `--list-modes`。
- **核心方法**：
  - `set_mode("chat" | "query")`: 切换普通聊天模式或知识库检索模式。
  - `talk(message)`: 发送单条消息。
  - `run(suite)`: 执行指定测试套件（支持传入测试套件名称字符串、类或实例）。

---

### 3. RAGFlow 客户端 (`ragflow_client.py`)

继承自 `openaiClient`，针对 RAGFlow 服务进行了适配。
- **命令行参数**：支持 `--model`, `--url`, `--test-suite` (`-t`), `--list-test`, `--list-modes`。

---

### 4. 测试套件与日志保存 (`test_suite.py`)

提供 `ChatContent` 基类、预设测试用例、附件路径校验、图片提取与保存工具函数及动态加载函数：

- **`user_content` 数据格式**：
  - `user_content` 为字典数组，每个字典包含 `message`（字符串提示词）与 `attachment_lists`（本地文件路径字符串数组）。
  - 执行每轮对话时，由 `test_suite.py` 自动校验 `attachment_lists` 中的本地文件是否存在；若文件不存在，会在日志中记录 `WARNING` 警告并将剩余部分正常发送给大模型。
  - `openAI_client.py` 支持将每轮对话中的 `message` 与 `attachment_lists` 附件一同发送给大模型；其余客户端仅使用纯文本 `message`。
- **动态加载函数**：
  - `test_suite.get_available_test_suites()`: 返回当前所有已定义的测试套件名称列表。
  - `test_suite.get_test_suite(name)`: 根据名称字符串动态实例化对应测试套件，若不存在则抛出包含可用列表的友好提示。
- **预设测试套件**：
  - `test_1`: 通用助手问答测试（11 个问题）
  - `test_2`: 客户服务与路由器产品咨询测试
  - `test_3`: 带指令与退出的交互测试
  - `test_4_network_device_dev`: 驱动开发与网络设备专项技术问答测试
  - `test_5_ping`: 身份与可用性探测问答测试
  - `test_6_draw`: 多模态文生图与识图两轮测试（第一轮生成图片并保存为 `logs/test6_output.png`，第二轮将该图片作为附件发送给大模型询问图中内容）
  - `test_99`: 路由配置与网络故障排障问答测试

#### 日志与图片保存机制
- **对话日志**：当测试运行完成（调用 `save_chat_content()`）后，对话历史自动保存至 `logs/chat_log_YYYYMMDD_HHMMSS.log`。
- **生成图片保存**：当要求模型画一幅画时，客户端会自动提取模型返回的图片并保存至 `logs/` 目录（如 `test_6_draw` 固定保存为 `logs/test6_output.png`，常规生成保存为 `logs/image_YYYYMMDD_HHMMSS.<ext>`），同时在对话日志中记录图片保存的完整路径。
- 若 `logs/` 文件夹不存在，程序将自动创建。

---

## 运行示例

### 示例 1：命令行运行 OpenAI 兼容客户端

#### 1.1 查看所有可用测试套件与模型
```bash
# 查看测试套件列表
python openAI_client.py --list-test

# 查询服务端全部可用的模型列表
python openAI_client.py --url "http://127.0.0.1:8081/v1" --list-modes
```

#### 1.2 执行指定测试套件（非流式）
```bash
python openAI_client.py \
  --url "http://127.0.0.1:8000/v1" \
  --model "meta-llama/Llama-3-8B-Instruct" \
  --api_key "sk-xxxxxx" \
  --test test_1
```

#### 1.3 执行指定测试套件（流式）
```bash
python openAI_client.py \
  --url "http://127.0.0.1:8081/v1" \
  --model "gemini-3.8-flash" \
  --stream \
  -t test_4_network_device_dev
```

#### 1.4 多模态画图并自动保存至 `logs/` 文件夹
```bash
# 方式 1：运行预设画图测试套件 test_6_draw
python openAI_client.py \
  --url "http://127.0.0.1:8317/v1" \
  --model "gemini-3.1-flash-image" \
  --api_key "sk-xxxxxx" \
  --test test_6_draw \
  --stream

# 方式 2：使用 --prompt (-p) 直接要求模型画一幅画
python openAI_client.py \
  --url "http://127.0.0.1:8317/v1" \
  --model "gemini-3.1-flash-image" \
  --api_key "sk-xxxxxx" \
  -p "请画一幅水墨风格的江南水乡春景图"
```

---

### 示例 2：使用脚本文件快捷运行 (`run.sh`)

`run.sh` 支持透传任意附加参数给 Python 客户端：

```bash
# 1. 查看可用测试套件
./run.sh --list-test

# 2. 列出服务端全部可用的模型列表
./run.sh --list-modes

# 3. 运行默认测试套件 (test_5_ping)
./run.sh

# 4. 指定运行 test_1 测试套件
./run.sh --test test_1

# 5. 指定运行 test_2 测试套件
./run.sh -t test_2
```

---

### 示例 3：Python 代码中调用并运行测试套件

客户端 `run()` 方法现已全面支持直接传入**测试套件名称字符串**、**类**或**实例**，无需硬编码实例化：

#### 3.1 调用 OpenAI 兼容服务
```python
from openAI_client import openaiClient
import test_suite

# 创建客户端实例
client = openaiClient(
    model="gemini-3.8-flash",
    url="http://127.0.0.1:8081/v1",
    api_key="sk-your-api-key",
    stream=True
)

# 方式 1：直接通过字符串名称指定测试套件 (推荐)
client.run("test_1")

# 方式 2：使用动态加载函数
suite = test_suite.get_test_suite("test_5_ping")
client.run(suite)

# 方式 3：传入测试类或实例
client.run(test_suite.test_5_ping)
```

#### 3.2 调用 AnythingLLM 服务（带知识库检索）
```python
from anything_llm_client import anythingllm_Client

# 创建 AnythingLLM 客户端
client = anythingllm_Client(
    host="127.0.0.1",
    port=8804,
    workspace_slug="my_network_kb",
    withcontext=True
)

# 设置为知识库检索模式并执行测试套件
client.set_mode("query")
client.run("test_4_network_device_dev")
```

---

### 示例 4：自定义测试用例

如果需要定义自己的提示词列表进行自动化测试，只需继承 `ChatContent`：

```python
from base_client import HTTPClient
from openAI_client import openaiClient
from test_suite import ChatContent

# 1. 定义自定义测试用例
class MyCustomTest(ChatContent):
    system_content = "你是一名网络架构师，回答请力求精简且专业。"
    user_content = [
        {"message": "请简述 BGP 协议在大型网络中的选路规则。", "attachment_lists": []},
        {"message": "OSPF 与 IS-IS 的主要区别是什么？", "attachment_lists": []},
        {"message": "请分析这张网络拓扑图中的单点故障风险。", "attachment_lists": ["logs/topology.png"]},
    ]

# 2. 初始化客户端并执行测试
client = openaiClient(
    model="gemini-3.8-flash",
    url="http://127.0.0.1:8081/v1",
    stream=True
)

test_case = MyCustomTest()
client.run(test_case)

# 对话内容将自动持久化到 logs/chat_log_YYYYMMDD_HHMMSS.log
```

---

## 日志管理

- **保存路径**：所有会话日志均存放在 `logs/` 目录下。
- **文件格式**：每轮对话包含一条系统记录、用户提问与模型回答，格式如下：
  ```text
  {'role': 'system', 'content': '你是一个helpful assistant.'}
  {'role': 'user', 'content': '你是谁，什么版本'}
  {'role': 'assistant', 'content': '我是由 Google 训练的大型语言模型...'}
  ```
- **自动忽略**：`logs/` 目录已被加入 `.gitignore`，不会提交到代码仓库中。

---

## Git 忽略配置

本仓库已配置忽略以下目录和临时文件：

- `logs/`：对话日志目录及 `*.log` 文件
- `__pycache__/`：Python 字节码编译缓存文件
- `run.sh`：本地运行及包含私有参数或 Key 的启动脚本
