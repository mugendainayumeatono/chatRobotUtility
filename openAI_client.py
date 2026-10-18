# /// script
# dependencies = [
#   "openai",
# ]
# ///

import openai
import os
import logging
import argparse

import test_suite
from base_client import HTTPClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s %(filename)s:%(lineno)d - %(message)s')

class openaiClient(HTTPClient):
    def __init__(self, model="default", temperature=0.7, url="", api_key=None, stream=False):
        """
        初始化聊天客户端
        参数：
            model: OpenAI 模型名称
            temperature: 控制输出的随机性（0-1）
            url: API 基础 URL
            api_key: API 密钥
            stream: 是否启用流式输出
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            self.api_key = "EMPTY"  # 保持原有逻辑，如果没有提供则默认为 EMPTY
        
        self.client = openai.Client(
            base_url=url if url else None,
            api_key=self.api_key
        )
        
        self.model = model
        self.temperature = temperature
        self.stream = stream

    def list_models(self):
        """
        获取服务端全部可用的模型列表
        返回：
            模型 ID 字符串列表
        """
        try:
            response = self.client.models.list()
            model_ids = []
            if hasattr(response, 'data'):
                for item in response.data:
                    if hasattr(item, 'id'):
                        model_ids.append(item.id)
                    elif isinstance(item, dict):
                        model_ids.append(item.get('id', str(item)))
                    else:
                        model_ids.append(str(item))
            else:
                for item in response:
                    if hasattr(item, 'id'):
                        model_ids.append(item.id)
                    elif isinstance(item, dict):
                        model_ids.append(item.get('id', str(item)))
                    else:
                        model_ids.append(str(item))
            return model_ids
        except Exception as e:
            logging.error(f"获取模型列表失败: {e}")
            return []


    def talk_init(self,test_suite):
        test_suite.add_messages({"role": "system", "content": test_suite.system_content})
        self._test_suite = test_suite
        self.talk(test_suite.system_content)

    def talk(self, user_input):
        """
        发送消息并获取回复
        参数：
            user_input: 用户输入的字符串
        返回：
            模型的回复内容
        """   
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._test_suite.messages,
                temperature=self.temperature,
                stream=self.stream
            )
            
            if self.stream:
                reply = ""
                try:
                    for chunk in response:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if hasattr(delta, 'content') and delta.content is not None:
                                reply += delta.content
                except Exception as e:
                    print(f"Error parsing stream: {e}")
                    if not reply:
                        return f"解析流响应时出错: {e}"
                return reply.strip()
            else:
                try:
                    reply = response.choices[0].message.content.strip()
                except Exception as e:
                    print(f"Error parsing response: {e}")
                    print(f"Full response: {response}")
                    return f"解析响应时出错: {e}"
                return reply

        except openai.OpenAIError as e:
            return f"发生错误: {e}"

# 测试代码
def main():
    parser = argparse.ArgumentParser(description="OpenAI 聊天客户端测试工具")
    parser.add_argument("--model", type=str, default="default", help="模型名称")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:30000/v1", help="API基础 URL")
    parser.add_argument("--api_key", type=str, help="API 密钥 (如果未提供，将尝试从环境变量 OPENAI_API_KEY 获取)")
    parser.add_argument("--stream", action="store_true", help="是否启用流式响应")
    parser.add_argument("--test-suite", "--test_suite", "--test", "-t", type=str, default="test_5_ping",
                        help=f"要执行的测试套件名称 (默认: test_5_ping，可选: {', '.join(test_suite.get_available_test_suites())})")
    parser.add_argument("--list-test", "--list-tests", "--list_tests", "--list_test", dest="list_test", action="store_true", help="列出所有可用的测试套件并退出")
    parser.add_argument("--list-modes", "--list-mode", "--list-models", "--list-model", "--list_modes", "--list_mode", dest="list_modes", action="store_true", help="列出全部可用的模型列表并退出")
    
    args = parser.parse_args()

    if args.list_test:
        print("可用的测试套件:")
        for name in test_suite.get_available_test_suites():
            print(f"  - {name}")
        return

    if args.list_modes:
        client = openaiClient(
            model=args.model,
            url=args.url,
            api_key=args.api_key,
            stream=args.stream
        )
        models = client.list_models()
        if models:
            print(f"服务端 ({args.url}) 可用模型列表 (共 {len(models)} 个):")
            for m in models:
                print(f"  - {m}")
        else:
            print(f"未能获取到模型列表，请检查服务地址 ({args.url}) 是否正常运行及 API Key 是否有效。")
        return

    client = openaiClient(
        model=args.model,
        url=args.url,
        api_key=args.api_key,
        stream=args.stream
    )
    try:
        suite = test_suite.get_test_suite(args.test_suite)
    except ValueError as e:
        logging.error(e)
        return

    client.run(suite)

def test():
    # 测试代码
    chat_content = test_suite.test_1()
    chat_content.add_messages({"role": "system", "content": chat_content.system_content})
    for i in range(len(chat_content.user_content)):
        user_input = chat_content.user_content[i]
        chat_content.add_messages({"role": "user", "content": user_input})
        reply = "dummy reply"  # 模拟模型的回复
        chat_content.add_messages({"role": "assistant", "content": reply})
    chat_content.save_chat_content()

if __name__ == "__main__":
    main()
    #test()
