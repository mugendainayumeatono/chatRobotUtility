import json
import http.client
from typing import Dict, Any
import logging

class HTTPClient:
    support_attachments = False

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
    
    def run(self, _test_suite):
        """
        运行交互式聊天循环
        参数：
            _test_suite: 测试套件实例、测试套件类、或测试套件名称字符串
        """
        if isinstance(_test_suite, str):
            import test_suite
            _test_suite = test_suite.get_test_suite(_test_suite)
        elif isinstance(_test_suite, type):
            _test_suite = _test_suite()

        logging.info(f"开始测试: {_test_suite.__class__.__name__}")
        self.talk_init(_test_suite)
        for i in range(len(_test_suite.user_content)):
            user_item = _test_suite.get_validated_user_input(i)
            if self.support_attachments:
                user_msg_record = {"role": "user", "content": user_item["message"]}
                if user_item["attachment_lists"]:
                    user_msg_record["attachment_lists"] = user_item["attachment_lists"]
                _test_suite.add_messages(user_msg_record)
                message = self.talk(user_item)
            else:
                text_message = user_item["message"]
                _test_suite.add_messages({"role": "user", "content": text_message})
                message = self.talk(text_message)
            _test_suite.add_messages({"role": "assistant", "content": f"{message}"})
        _test_suite.save_chat_content()
        if getattr(_test_suite, "saved_images", None):
            logging.info(f"本次测试共保存 {len(_test_suite.saved_images)} 张图片至 logs 目录: {[str(p) for p in _test_suite.saved_images]}")
        logging.info(f"测试结束: {_test_suite.__class__.__name__}")