from typing import Dict, Any
import os
import logging
import uuid
from datetime import datetime

import test_suite
from base_client import HTTPClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s %(filename)s:%(lineno)d - %(message)s')

class anythingllm_Client(HTTPClient):
    def __init__(self, host: str = 'localhost', port: int = 8000, workspace_slug: str = 'default', withcontext: bool = True):
        super().__init__(host, port)
        self.workspace_slug = workspace_slug
        self.thread_slug = None
        self.withcontext = withcontext

        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_key = "RYDVADM-T5K4TMA-H0QQ0V9-46GQ64S"

        self.sessionId = uuid.uuid4()
        self.mode = "chat"
        self.userId = 1

    def creat_headers(self) -> Dict[str, Any]:
        """
        创建请求头
        """
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        return headers
    
    def data_analyze(self, message: str):
        """
        分析响应内容
        """
        source_title = []
        if message is None:
            logging.error("Error: No message in response")
            return ""
        if isinstance(message, dict):
            error = message.get("error", None)
            if error is not None:
                return error
            id = message.get("id", None)
            type = message.get("type", None)
            closed = message.get("closed", None)
            chatId = message.get("chatId", None)
            textResponse = message.get("textResponse", "")
            sources = message.get("sources", None)
            if sources is not None:
                for source in sources:
                    source_title.append(source.get("title", None))
            metrics = message.get("metrics", None)
            if metrics is not None:
                prompt_tokens = metrics.get("prompt_tokens", None)
                completion_tokens = metrics.get("completion_tokens", None)
                total_tokens = metrics.get("total_tokens", None)
                outputTps = metrics.get("outputTps", None)
                duration = metrics.get("duration", None)
            textResponse = textResponse + "ref: \n"
            for each in source_title:
                textResponse = textResponse + each + "  "
            return textResponse
        
    def talk(self, message: str) -> Dict[str, Any]:
        """
        发送消息并获取回复
        参数：
            message: 用户输入的字符串
        返回：
            模型的回复内容
        """
        if self.withcontext:
            return self.talk_with_context(message)
        else:
            return self.talk_without_context(message)
        
    def talk_init(self,test_suite):
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        if self.withcontext:
            self.creat_new_thread(current_time)

    def talk_without_context(self, message: str) -> Dict[str, Any]:
        data = {
                "message": f"{message}",
                "mode": f"{self.mode}",
                "sessionId": f"{self.sessionId}",
                "reset": False
                }
        chat_in_new_thread = f"/api/v1/workspace/{self.workspace_slug}/chat"
        ret = self.send_post(chat_in_new_thread, data)
        data = self.response_error_check(ret)
        message = self.data_analyze(data)
        return message
    
    def talk_with_context(self, message: str) -> Dict[str, Any]:
        data = {
                "message": f"{message}",
                "mode": f"{self.mode}",
                "userId": self.userId,
                "reset": False
                }
        chat_with_context = f"/api/v1/workspace/{self.workspace_slug}/thread/{self.thread_slug}/chat"
        ret = self.send_post(chat_with_context, data)
        data = self.response_error_check(ret)
        message = self.data_analyze(data)
        return message

    def set_mode(self, mode: str):
        """
        设置模式
        """
        if mode in ["chat", "query"]:
            self.mode = mode
        else:
            raise ValueError("Invalid mode. Choose 'chat' or 'query'.")
        
    def creat_new_thread(self, thrad_name: str = 'default') -> bool:
        slug = uuid.uuid4()
        data = {
                "userId": self.userId,
                "name": thrad_name,
                "slug": f"{slug}",
                }
        create_new_thread = f"/api/v1/workspace/{self.workspace_slug}/thread/new"
        ret = self.send_post(create_new_thread , data)
        data = self.response_error_check(ret)
        if data is not None:
            thread = data.get("thread", None)
            if thread is not None:
                logging.info(f"创建会话成功: {thread}")
                self.thread_slug = thread.get("slug", None)
                return True
        logging.error(f"创建会话失败: {data}")
        return False

def main():
    client1 = anythingllm_Client(host = 'localhost', port = 8804, workspace_slug = 'txt_h1')
    #client1.set_mode("query")
    client1.run(test_suite.test_4_network_device_dev())
    client2 = anythingllm_Client(host = 'localhost', port = 8804, workspace_slug = 'txt_h5')
    #client2.set_mode("query")
    client2.run(test_suite.test_4_network_device_dev())
    #client2.run(test_suite.test_99())

if __name__ == "__main__":
    main()
