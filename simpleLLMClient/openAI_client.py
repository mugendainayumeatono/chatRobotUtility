import openai
import os
import logging

import test_suite
from base_client import HTTPClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s %(filename)s:%(lineno)d - %(message)s')

class openaiClient(HTTPClient):
    def __init__(self, model="default", temperature=0.7,url=""):
        """
        初始化聊天客户端
        参数：
            model: OpenAI 模型名称
            temperature: 控制输出的随机性（0-1）
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_key = "EMPTY"
        openai.api_key = self.api_key
        if not openai.api_key:
            raise ValueError("请设置 OPENAI_API_KEY 环境变量或直接提供密钥")
        
        self.client = openai.Client(base_url=url, api_key=openai.api_key)
        
        self.model = model
        self.temperature = temperature

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
                temperature=self.temperature
            )
            reply = response.choices[0].message.content.strip()
            return reply
        
        except openai.error.OpenAIError as e:
            return f"发生错误: {e}"

# 测试代码
def main():
    client = openaiClient(model="default", url="http://127.0.0.1:30000/v1")
    client.run(test_suite.test_2())

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
