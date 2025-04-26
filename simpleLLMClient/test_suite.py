import logging
import datetime
from pathlib import Path

class ChatContent:
    system_content = ""
    user_content = []
    def __init__(self):
        self.messages = []

    def format_output(self, content):
        """
        格式化输出聊天内容
        """
        if isinstance(content, dict):
            role = content.get("role", "unknown")
            message = content.get("content", "")
            logging.info(f"{role}: {message}")
        else:
            logging.info(content)

    def truncate_before_think(self, text):
        # 查找 </think> 的位置
        index = text.find("</think>")
        if index != -1:  # 如果找到了 </think>
            # 返回 </think> 及其之后的内容
            return text[index + 8:]
        else:
            # 如果没找到，返回原字符串
            return text

    def add_messages(self, input, is_with_think=False):
        """
        记录聊天内容
        参数：
            input: 用户输入的字符串
        """
        if not is_with_think:
            content = input.get("content", "")
            content = self.truncate_before_think(content)
            input["content"] = content

        self.messages.append(input)
        self.format_output(input)

    def save_chat_content(self):
        """
        保存聊天内容到文件
        """
        # 获取当前日期时间
        current_time = datetime.datetime.now()
        # 格式化为字符串（例如：20250406_143022）
        filename = current_time.strftime("chat_log_%Y%m%d_%H%M%S") + ".log"
        file_path = Path(filename)
        with file_path.open("w", encoding="utf-8") as f:
            for content in self.messages:
                f.write(str(content).replace("\\n", "\n") + "\n")
        logging.info(f"聊天内容已保存到 {file_path}")

class test_1(ChatContent):
    system_content = "你是一个helpful assistant."
    user_content = [
        "你能帮我写一个Python脚本吗？",
        "请给我一些关于机器学习的建议。",
        "你认为未来的科技会是什么样子？",
        "如何提高我的编程技能？",
        "你能推荐一些好书吗？",
        "请告诉我一些关于人工智能的有趣事实。",
        "你能给我讲个笑话吗？",
        "你喜欢什么类型的音乐？",
        "你能帮我解决一个数学问题吗？",
        "你能告诉我一些关于历史的事情吗？",
        "你能给我一些旅行建议吗？",
    ]

class test_2(ChatContent):
    user_content = [
        "你是什么？",
        "你能做什么",
        "今天的日期是？",
        "@agent 今天的日期是？",
        "你们的产品包括哪些",
        "我对你们的产品有疑问",
        "我想问关于AR600设备的相关内容",
        "我刚刚咨询的设备型号是什么",
        "配置GRE隧道，并在隧道上运行静态路由实现互通的示例",
        "配置采用HWTACACS协议对Telnet用户进行命令行授权示例",
        "我该如何升级系统文件",
        "我想通过ACL规则限制访问外网",
        "上面给出的信息适用于什么型号的设备？",
        "我刚刚咨询的设备型号是什么"
        "使用5G链接公网时报错了",
        "部署语音网关时遇到问题",
    ]

class test_3(ChatContent):
    user_content = [
        "@agent",
        "你是什么？",
        "你能做什么",
        "今天的日期是？",
        "你们的产品包括哪些",
        "我对你们的产品有疑问",
        "我想问关于AR600设备的相关内容",
        "我刚刚咨询的设备型号是什么",
        "配置GRE隧道，并在隧道上运行静态路由实现互通的示例",
        "配置采用HWTACACS协议对Telnet用户进行命令行授权示例",
        "我该如何升级系统文件",
        "我想通过ACL规则限制访问外网",
        "上面给出的信息适用于什么型号的设备？",
        "我刚刚咨询的设备型号是什么"
        "使用5G链接公网时报错了",
        "部署语音网关时遇到问题",
        "/exit"
    ]

class test_4_network_device_dev(ChatContent):
    user_content = [
        "你是什么？",
        "你能做什么",
        "今天的日期是？",
        "@agent 今天的日期是？",
        "你的知识库里现在有哪些知识？",
        "NDIS支持哪些类型的网络接口卡(NIC)驱动程序",
        "NDIS微端口提供的电源管理（PM）服务包括哪些内容",
        "什么是快速转发路径",
        "数据传输时应该如何做中断处理？",
        "如何在微端口驱动程序上实现LBFO",
        "在主微端口失效后提升一个次微端口,应该怎么做？",
    ]

class test_99(ChatContent):
    user_content = [
        "配置GRE隧道，并在隧道上运行静态路由实现互通的示例",
        "配置采用HWTACACS协议对Telnet用户进行命令行授权示例",
        "我该如何升级系统文件",
        "我想通过ACL规则限制访问外网",
        "上面给出的信息适用于什么型号的设备？",
        "我刚刚咨询的设备型号是什么"
        "使用5G链接公网时报错了",
        "部署语音网关时遇到问题",
    ]