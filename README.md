# ChatRobotUtility

一个用于与各种大语言模型 (LLM) 引擎交互并运行自动化测试套件的实用工具库。

## 项目结构：`simpleLLMClient`

该目录提供了一个轻量级的 LLM 客户端库，支持多种后端引擎，并集成了自动化交互测试功能。

### 1. 组件概述

- **`base_client.py`**: 库的核心基础。包含 `HTTPClient` 类，提供通用的 POST 请求处理、错误检查以及用于自动化测试的核心 `run` 循环。
- **`openAI_client.py`**: 适配 OpenAI 兼容 API（如 vLLM, Ollama, DeepSeek 等）的客户端，基于 `openai` Python SDK 实现。
- **`anything-llm_client.py`**: 专门针对 AnythingLLM 开发的客户端。支持工作区（Workspace）和线程（Thread）管理，并能解析 RAG（检索增强生成）的源引用。
- **`ragflow_client.py`**: 对接 RAGFlow 服务的客户端，继承自 `openaiClient`。
- **`test_suite.py`**: 测试内容管理器。定义了 `ChatContent` 类用于管理消息历史，并包含多个预设测试用例（`test_1` 到 `test_99`），涵盖通用助手、网络设备排障等场景。
- **`deepDeekOverOpenAI.py`**: 一个简易脚本，展示如何直接通过 OpenAI 风格的 API 调用特定服务。

### 2. 架构与调用流程

#### 类继承结构
```text
HTTPClient (base_client.py)
├── openaiClient (openAI_client.py)
│   └── ragflowClient (ragflow_client.py)
└── anythingllm_Client (anything-llm_client.py)
```

#### 执行逻辑
1.  **初始化**: 实例化具体的客户端（如 `anythingllm_Client`），配置服务器地址和认证信息。
2.  **执行测试**: 调用 `client.run(test_suite_instance)`。
3.  **循环交互**: `run()` 方法会遍历测试套件中的 `user_content`，通过 `talk()` 发送请求并收集响应。
4.  **日志记录**: 所有交互内容都会实时输出到控制台，并自动保存为带时间戳的 `.log` 文件（例如 `chat_log_20260508_120000.log`）。

### 3. 使用指南

#### 环境准备
安装必要的依赖：
```bash
pip install -r simpleLLMClient/requirements.txt
```

#### 快速上手

**使用 OpenAI 兼容接口：**
```python
from simpleLLMClient.openAI_client import openaiClient
import simpleLLMClient.test_suite as test_suite

client = openaiClient(model="default", url="http://127.0.0.1:30000/v1")
client.run(test_suite.test_2())
```

**使用 AnythingLLM（支持 RAG）：**
```python
from simpleLLMClient.anything_llm_client import anythingllm_Client
import simpleLLMClient.test_suite as test_suite

client = anythingllm_Client(host='localhost', port=8804, workspace_slug='my_workspace')
client.run(test_suite.test_4_network_device_dev())
```

### 4. 关键特性
- **自动化测试**: 轻松运行一系列 Prompt 以验证模型表现。
- **RAG 支持**: `anythingllm_Client` 能够自动提取并展示知识库引用来源。
- **日志持久化**: 自动保存对话记录，方便复盘和调试。

## 开发注意事项
- **安全性**: 避免在代码中硬编码 API Key，建议使用环境变量。
- **可扩展性**: 若要支持新引擎，只需继承 `HTTPClient`（或 `openaiClient`）并实现 `talk()` 和 `talk_init()` 方法。
