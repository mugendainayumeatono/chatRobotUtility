import json
import http.client
from typing import Dict, Any
import logging

class HTTPClient:
    def __init__(self, host: str = 'localhost', port: int = 8000):
        self.host = host
        self.port = port
        
    def creat_headers(self) -> Dict[str, Any]:
        """
        创建请求头
        """
        headers = {
            'accept': 'application/json'
        }
        return headers
    
    def send_post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # 创建连接
            conn = http.client.HTTPConnection(self.host, self.port)
            
            # 准备请求
            headers = self.creat_headers()

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

    def data_analyze(self, message: str):
        """
        分析响应内容
        """
        if message is None:
            logging.error("Error: No message in response")
            return ""
        return message
    
    def talk(self, message: str) -> Dict[str, Any]:
        data = {'message': f"{message}"}
        chat_with_context = f"/api/v1/workspace/{self.workspace_slug}/thread/{self.thread_slug}/chat"
        ret = self.send_post(chat_with_context, data)
        data = self.response_error_check(ret)
        message = self.data_analyze(data)
        return message

    def talk_init(self,test_suite):
        pass
    
    def run(self,_test_suite):
        """
        运行交互式聊天循环
        """
        logging.info("开始测试")
        self.talk_init(_test_suite)
        for i in range(len(_test_suite.user_content)):
            user_input = _test_suite.user_content[i]
            _test_suite.add_messages({"role":"user", "content": f"{user_input}"})
            message = self.talk(user_input)
            _test_suite.add_messages({"role":"assistant", "content": f"{message}"})
        _test_suite.save_chat_content()
        logging.info("测试结束")