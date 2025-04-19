import json
import http.client
import urllib.parse
import threading
from typing import Dict, Any
import os
from pathlib import Path
import logging
import datetime
import uuid

import test_suite

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s %(filename)s:%(lineno)d - %(message)s')

class HTTPClient:
    def __init__(self, host: str = 'localhost', port: int = 8000, workspace_slug: str = 'default', withcontext: bool = True):
        self.host = host
        self.port = port
        self.workspace_slug = workspace_slug
        self.thread_slug = None
        self.withcontext = withcontext

        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_key = "RYDVADM-T5K4TMA-H0QQ0V9-46GQ64S"

        self.sessionId = uuid.uuid4()
        self.mode = "chat"
        self.userId = 1

    def send_post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # 创建连接
            conn = http.client.HTTPConnection(self.host, self.port)
            
            # 准备请求
            headers = {
                        'accept': 'application/json',
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {self.api_key}'
                    }
            body = json.dumps(data).encode('utf-8')
            
            logging.debug(path)
            logging.debug(headers)
            logging.debug(body)
            # 发送POST请求
            conn.request('POST', path, body, headers)
            
            # 获取响应
            response = conn.getresponse()
            response_data = response.read().decode('utf-8')
            conn.close()
            logging.debug(response_data)
            
            # 解析响应
            try:
                return {
                    "status_code": response.status,
                    "data": json.loads(response_data)
                }
            except json.JSONDecodeError:
                return {
                    "status_code": response.status,
                    "data": {"error": "Invalid response format"}
                }
                
        except Exception as e:
            return {
                "status_code": 500,
                "data": {"error": f"Client error: {str(e)}"}
            }
    def response_error_check(self, response: Dict[str, Any]):
        """
        检查响应是否有错误
        """
        data = response.get("data")
        if response.get("status_code") != 200:
            logging.error(f"Error: {data}")
            return None

        if data is None:
            logging.error("Error: No data in response")
            return None
        else:
            return data

    def creat_new_thread(self, thrad_name: str = 'default') -> bool:
        slug = uuid.uuid4()
        data = {
                "userId": self.userId,
                "name": thrad_name,
                "slug": f"{slug}",
                }
        self.create_new_thread = f"/api/v1/workspace/{self.workspace_slug}/thread/new"
        ret = self.send_post(self.create_new_thread , data)
        data = self.response_error_check(ret)
        if data is not None:
            thread = data.get("thread", None)
            if thread is not None:
                logging.info(f"创建会话成功: {thread}")
                self.thread_slug = thread.get("slug", None)
                return True
        logging.error(f"创建会话失败: {data}")
        return False

    def data_analyze(self, message: str):
        """
        分析响应内容
        """
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
            metrics = message.get("metrics", None)
            if metrics is not None:
                prompt_tokens = metrics.get("prompt_tokens", None)
                completion_tokens = metrics.get("completion_tokens", None)
                total_tokens = metrics.get("total_tokens", None)
                outputTps = metrics.get("outputTps", None)
                duration = metrics.get("duration", None)
            return textResponse

    def talk(self, message: str) -> Dict[str, Any]:
        data = {
                "message": f"{message}",
                "mode": f"{self.mode}",
                "sessionId": f"{self.sessionId}",
                "reset": False
                }
        self.chat_in_new_thread = f"/api/v1/workspace/{self.workspace_slug}/chat"
        ret = self.send_post(self.chat_in_new_thread, data)
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
        self.chat_with_context = f"/api/v1/workspace/{self.workspace_slug}/thread/{self.thread_slug}/chat"
        ret = self.send_post(self.chat_with_context, data)
        data = self.response_error_check(ret)
        message = self.data_analyze(data)
        return message
    
    def run(self):
        """
        运行交互式聊天循环
        """
        logging.info("开始测试")
        _test_suite = test_suite.test_2()
        if self.withcontext:
            self.creat_new_thread()
        for i in range(len(_test_suite.user_content)):
            user_input = _test_suite.user_content[i]
            _test_suite.add_messages({"role":"user", "content": f"{user_input}"})
            if self.withcontext:
                message = self.talk_with_context(user_input)
            else:
                message = self.talk(user_input)
            _test_suite.add_messages({"role":"assistant", "content": f"{message}"})
        _test_suite.save_chat_content()
        logging.info("测试结束")

def main():
    client1 = HTTPClient(host = 'localhost', port = 8804, workspace_slug = 'deepseek7b')
    client1.run()
    client2 = HTTPClient(host = 'localhost', port = 8804, workspace_slug = 'test_for_me')
    client2.run()

if __name__ == "__main__":
    main()
