# /// script
# dependencies = [
#   "openai",
# ]
# ///

import argparse
import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, List, Optional

import openai

import test_suite
from base_client import HTTPClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s %(filename)s:%(lineno)d - %(message)s')


def encode_local_image_to_data_uri(image_path: str) -> Optional[str]:
    """
    将本地图片文件编码为 data:image/...;base64,... URI
    """
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        logging.error(f"本地图片文件不存在: {image_path}")
        return None
    if path.stat().st_size > test_suite.MAX_IMAGE_SIZE_BYTES:
        logging.error(f"本地图片文件过大: {image_path}")
        return None
    image_bytes = path.read_bytes()
    mime_type = test_suite.detect_image_mime(image_bytes)
    b64_str = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64_str}"


def build_multimodal_content(text: str, image_sources: Optional[List[str]] = None) -> Any:
    """
    构建 OpenAI 兼容的多模态消息 content 列表
    参数：
        text: 文本提示词
        image_sources: 本地图片路径、HTTP(S) 链接或 data URI 列表
    """
    if not image_sources:
        return text

    content_parts = []
    if text:
        content_parts.append({"type": "text", "text": text})

    for src in image_sources:
        if not src:
            continue
        if src.startswith(("http://", "https://", "data:")):
            url_val = src
        else:
            url_val = encode_local_image_to_data_uri(src)
            if not url_val:
                continue
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": url_val},
        })
    return content_parts


class openaiClient(HTTPClient):
    def __init__(self, model="default", temperature=0.7, url="", api_key=None, stream=False, log_dir=None):
        """
        初始化聊天客户端
        参数：
            model: OpenAI 模型名称
            temperature: 控制输出的随机性（0-1）
            url: API 基础 URL
            api_key: API 密钥
            stream: 是否启用流式输出
            log_dir: 日志与生成图片的保存目录（默认为 logs 文件夹）
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
        self.log_dir = log_dir
        self._test_suite: Optional[test_suite.ChatContent] = None

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

    def _get_target_log_dir(self):
        if self._test_suite is not None and getattr(self._test_suite, "log_dir", None) is not None:
            return self._test_suite.log_dir
        return self.log_dir

    def _save_unique_image(self, source: Any, seen_hashes: set, saved_paths: List[Path]) -> Optional[Path]:
        """
        提取图片字节并在当前轮次去重后保存至 logs 文件夹
        """
        extracted = test_suite.extract_image_bytes_from_source(source)
        if not extracted:
            return None
        image_bytes, mime_type = extracted
        digest = hashlib.sha256(image_bytes).hexdigest()
        if digest in seen_hashes:
            return None

        path = test_suite.save_image_bytes(
            image_bytes,
            mime_type=mime_type,
            log_dir=self._get_target_log_dir(),
        )
        if path is not None:
            seen_hashes.add(digest)
            saved_paths.append(path)
            if self._test_suite is not None and hasattr(self._test_suite, "saved_images"):
                self._test_suite.saved_images.append(path)
        return path

    def _extract_from_message_or_delta(
        self,
        obj: Any,
        reply_parts: List[str],
        seen_hashes: set,
        saved_paths: List[Path],
    ) -> None:
        """
        从非流式 message 或流式 delta 对象中提取文本和图片
        """
        if obj is None:
            return

        content = getattr(obj, "content", None)
        if content is None and isinstance(obj, dict):
            content = obj.get("content")

        if isinstance(content, str):
            reply_parts.append(content)
        elif isinstance(content, list):
            for part in content:
                part_dict = part.model_dump() if hasattr(part, "model_dump") else part
                if isinstance(part_dict, dict):
                    part_type = part_dict.get("type", "")
                    if part_type in ("text", "output_text", "input_text") and part_dict.get("text") is not None:
                        reply_parts.append(str(part_dict["text"]))
                    else:
                        self._save_unique_image(part_dict, seen_hashes, saved_paths)
                elif isinstance(part, str):
                    reply_parts.append(part)

        # 提取扩展字段中的 images 列表（如 OpenAI 兼容多模态代理返回的 message.images / delta.images）
        images = getattr(obj, "images", None)
        if images is None:
            if hasattr(obj, "model_dump"):
                images = obj.model_dump().get("images")
            elif isinstance(obj, dict):
                images = obj.get("images")

        if isinstance(images, list):
            for img_item in images:
                self._save_unique_image(img_item, seen_hashes, saved_paths)

    def _finalize_reply_with_images(
        self,
        raw_reply: str,
        seen_hashes: set,
        saved_paths: List[Path],
    ) -> str:
        """
        处理文本内嵌图片（Markdown / Data URI）并将所有已保存图片的本地路径附加到回复中
        """
        cleaned_reply, text_image_paths = test_suite.extract_and_save_images_from_text(
            raw_reply,
            log_dir=self._get_target_log_dir(),
            seen_hashes=seen_hashes,
        )
        for p in text_image_paths:
            saved_paths.append(p)
            if self._test_suite is not None and hasattr(self._test_suite, "saved_images"):
                self._test_suite.saved_images.append(p)

        cleaned_reply = cleaned_reply.strip()
        for path in saved_paths:
            path_str = str(path)
            if path_str not in cleaned_reply:
                note = f"[图片已保存至: {path_str}]"
                cleaned_reply = f"{cleaned_reply}\n{note}" if cleaned_reply else note

        return cleaned_reply

    def _prepare_messages(self, user_input: Any) -> List[dict]:
        """
        准备发送给 OpenAI 接口的 messages 列表，支持直接调用 talk() 以及本地图片路径自动转码
        """
        if self._test_suite is not None and getattr(self._test_suite, "messages", None):
            raw_messages = self._test_suite.messages
        else:
            raw_messages = [{"role": "user", "content": user_input}]

        prepared = []
        for msg in raw_messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # 如果 system 消息为空字符串，跳过向后端发送空 system 消息以兼容各类多模态模型
            if role == "system" and content == "":
                continue
            if isinstance(content, list):
                normalized_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        img_url_obj = part.get("image_url", {})
                        url = img_url_obj.get("url", "") if isinstance(img_url_obj, dict) else str(img_url_obj)
                        if url and not url.startswith(("http://", "https://", "data:")):
                            encoded = encode_local_image_to_data_uri(url)
                            if encoded:
                                part = {
                                    "type": "image_url",
                                    "image_url": {"url": encoded},
                                }
                    normalized_parts.append(part)
                prepared.append({"role": role, "content": normalized_parts})
            else:
                prepared.append({"role": role, "content": content})

        if not prepared and user_input is not None:
            prepared.append({"role": "user", "content": user_input})

        return prepared

    def talk_init(self, test_suite):
        test_suite.add_messages({"role": "system", "content": test_suite.system_content})
        self._test_suite = test_suite

    def talk(self, user_input):
        """
        发送消息并获取回复（支持多模态输入及模型生成图片自动保存至 logs 文件夹）
        参数：
            user_input: 用户输入的字符串或多模态内容列表
        返回：
            模型的回复内容（若包含生成的图片，会自动保存至 logs 文件夹并在回复中附带保存路径）
        """
        try:
            messages = self._prepare_messages(user_input)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                stream=self.stream
            )

            reply_parts: List[str] = []
            seen_hashes: set = set()
            saved_paths: List[Path] = []

            if self.stream:
                try:
                    for chunk in response:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            self._extract_from_message_or_delta(delta, reply_parts, seen_hashes, saved_paths)
                except Exception as e:
                    print(f"Error parsing stream: {e}")
                    if not reply_parts and not saved_paths:
                        return f"解析流响应时出错: {e}"
                return self._finalize_reply_with_images("".join(reply_parts), seen_hashes, saved_paths)
            else:
                try:
                    if response.choices and len(response.choices) > 0:
                        message = response.choices[0].message
                        self._extract_from_message_or_delta(message, reply_parts, seen_hashes, saved_paths)
                    elif hasattr(response, "data") and isinstance(response.data, list):
                        for item in response.data:
                            self._save_unique_image(item, seen_hashes, saved_paths)
                except Exception as e:
                    print(f"Error parsing response: {e}")
                    print(f"Full response: {response}")
                    if not reply_parts and not saved_paths:
                        return f"解析响应时出错: {e}"
                return self._finalize_reply_with_images("".join(reply_parts), seen_hashes, saved_paths)

        except openai.OpenAIError as e:
            return f"发生错误: {e}"


# 测试代码
def main():
    parser = argparse.ArgumentParser(description="OpenAI 聊天客户端测试工具（支持多模态对话与图片生成保存）")
    parser.add_argument("--model", type=str, default="default", help="模型名称")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:30000/v1", help="API基础 URL")
    parser.add_argument("--api_key", type=str, help="API 密钥 (如果未提供，将尝试从环境变量 OPENAI_API_KEY 获取)")
    parser.add_argument("--stream", action="store_true", help="是否启用流式响应")
    parser.add_argument("--test-suite", "--test_suite", "--test", "-t", type=str, default="test_5_ping",
                        help=f"要执行的测试套件名称 (默认: test_5_ping，可选: {', '.join(test_suite.get_available_test_suites())})")
    parser.add_argument("--prompt", "-p", type=str, default=None, help="直接发送单条提示词（例如要求模型画一幅画），不指定则运行测试套件")
    parser.add_argument("--image", "-i", type=str, nargs="*", default=None, help="附加的多模态输入图片路径或 URL（可指定多个）")
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

    if args.prompt is not None:
        suite = test_suite.ChatContent()
        user_item = build_multimodal_content(args.prompt, args.image) if args.image else args.prompt
        suite.user_content = [user_item]
        client.run(suite)
        return

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

