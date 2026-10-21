# /// script
# dependencies = [
#   "openai",
# ]
# ///

import argparse
import base64
import hashlib
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, List, Optional

import openai

import test_suite
from base_client import HTTPClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s %(filename)s:%(lineno)d - %(message)s')

KNOWN_BINARY_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a",
    ".mp4", ".mkv", ".avi", ".mov", ".webm",
    ".bin", ".exe", ".dll", ".so", ".dylib", ".pyc", ".wasm",
}


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


def encode_attachment_part(file_path: str) -> Optional[dict]:
    """
    将本地附件文件编码为 OpenAI chat.completions 支持的 content 块：
    - 图片文件 -> {"type": "image_url", "image_url": {"url": "data:image/...;base64,..."}}
    - 文本文件 -> {"type": "text", "text": "[附件文件: ...]\n..."}
    - 其他二进制文件（如 PDF 等） -> {"type": "file", "file": {"filename": ..., "file_data": "data:...;base64,..."}}
    """
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        logging.warning(f"本地附件文件不存在: {file_path}")
        return None
    if path.stat().st_size > test_suite.MAX_IMAGE_SIZE_BYTES:
        logging.error(f"本地附件文件过大: {file_path}")
        return None

    file_bytes = path.read_bytes()
    guessed_mime, _ = mimetypes.guess_type(str(path))

    # 1. 检测是否为图片格式
    if test_suite.detect_image_extension(file_bytes, guessed_mime) is not None:
        mime_type = test_suite.detect_image_mime(file_bytes)
        b64_str = base64.b64encode(file_bytes).decode("ascii")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{b64_str}"},
        }

    # 2. 检测是否为可读文本文件
    ext_lower = path.suffix.lower()
    if ext_lower not in KNOWN_BINARY_EXTENSIONS and b"\x00" not in file_bytes[:8192]:
        try:
            text_content = file_bytes.decode("utf-8")
            return {
                "type": "text",
                "text": f"[附件文件: {path.name}]\n{text_content}",
            }
        except UnicodeDecodeError:
            pass

    # 3. 其他二进制文件（如 PDF 等）使用 file 类型传递
    mime_type = guessed_mime or "application/octet-stream"
    b64_str = base64.b64encode(file_bytes).decode("ascii")
    return {
        "type": "file",
        "file": {
            "filename": path.name,
            "file_data": f"data:{mime_type};base64,{b64_str}",
        },
    }


def build_multimodal_content(text: str, attachment_lists: Optional[List[str]] = None) -> Any:
    """
    构建 OpenAI 兼容的多模态消息 content 列表
    参数：
        text: 文本提示词 (message)
        attachment_lists: 本地附件文件路径列表
    """
    if not attachment_lists:
        return text

    content_parts = []
    if text:
        content_parts.append({"type": "text", "text": text})

    for src in attachment_lists:
        if not src:
            continue
        part = encode_attachment_part(src)
        if part is not None:
            content_parts.append(part)

    if not content_parts:
        return text
    return content_parts


class openaiClient(HTTPClient):
    support_attachments = True

    def __init__(self, model="default", temperature=0.7, url="", api_key=None, stream=False, log_dir=None, image_model="dall-e-3"):
        """
        初始化聊天客户端
        参数：
            model: OpenAI 模型名称
            temperature: 控制输出的随机性（0-1）
            url: API 基础 URL
            api_key: API 密钥
            stream: 是否启用流式输出
            log_dir: 日志与生成图片的保存目录（默认为 logs 文件夹）
            image_model: 文生图模型名称（默认 dall-e-3）
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            self.api_key = "EMPTY"  # 保持原有逻辑，如果没有提供则默认为 EMPTY

        self.client = openai.Client(
            base_url=url if url else None,
            api_key=self.api_key
        )

        self.model = model
        self.image_model = image_model
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

    def _get_target_image_filename(self) -> Optional[str]:
        if self._test_suite is not None:
            return getattr(self._test_suite, "image_filename", None)
        return None

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
            filename=self._get_target_image_filename(),
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
            filename=self._get_target_image_filename(),
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
        准备发送给 OpenAI 接口的 messages 列表，将每轮的 message 与 attachment_lists 组装发送给大模型
        """
        if self._test_suite is not None and getattr(self._test_suite, "messages", None):
            raw_messages = self._test_suite.messages
        else:
            if isinstance(user_input, dict):
                validated = test_suite.ChatContent().validate_user_input(user_input)
                raw_messages = [
                    {
                        "role": "user",
                        "content": validated["message"],
                        "attachment_lists": validated["attachment_lists"],
                    }
                ]
            else:
                raw_messages = [{"role": "user", "content": str(user_input)}]

        prepared = []
        for msg in raw_messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "user")
            content = msg.get("content", "")
            attachment_lists = msg.get("attachment_lists", [])
            # 如果 system 消息为空字符串，跳过向后端发送空 system 消息以兼容各类多模态模型
            if role == "system" and content == "":
                continue
            if attachment_lists:
                multimodal_content = build_multimodal_content(str(content), attachment_lists)
                prepared.append({"role": role, "content": multimodal_content})
            else:
                prepared.append({"role": role, "content": content})

        return prepared

    def talk_init(self, test_suite):
        test_suite.add_messages({"role": "system", "content": test_suite.system_content})
        self._test_suite = test_suite

    def talk(self, user_input):
        """
        发送消息并获取回复（支持上传 attachment_lists 中的本地文件及模型生成图片自动保存至 logs 文件夹）
        参数：
            user_input: 用户输入字典（包含 message 和 attachment_lists）
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

    def draw(self, user_input):
        """
        支持绘画的模型交互函数：
        当输入为画图需求时，调用图片生成接口（如 client.images.generate）生成并保存图片；
        若包含已有附件（如多模态对已生成图片的追问）或文生图接口调用失败时，回退至纯文本/多模态对话接口。
        参数：
            user_input: 用户输入字典（包含 message 和 attachment_lists）或字符串
        返回：
            模型回复或图片保存路径说明
        """
        if isinstance(user_input, dict):
            prompt = str(user_input.get("message", ""))
            attachments = user_input.get("attachment_lists", [])
        else:
            prompt = str(user_input)
            attachments = []

        # 如果包含附件列表，说明是对已有图片/文件的多模态追问，使用纯文字/多模态对话函数
        if attachments:
            return self.talk(user_input)

        try:
            image_model = self.image_model or "dall-e-3"
            response = self.client.images.generate(
                model=image_model,
                prompt=prompt,
                n=1,
            )

            seen_hashes: set = set()
            saved_paths: List[Path] = []
            revised_prompt = ""

            if hasattr(response, "data") and isinstance(response.data, list):
                for item in response.data:
                    self._save_unique_image(item, seen_hashes, saved_paths)
                    if hasattr(item, "revised_prompt") and item.revised_prompt:
                        revised_prompt = item.revised_prompt
                    elif isinstance(item, dict) and item.get("revised_prompt"):
                        revised_prompt = item["revised_prompt"]

            if saved_paths:
                notes = [f"[图片已保存至: {p}]" for p in saved_paths]
                result_text = "\n".join(notes)
                if revised_prompt:
                    result_text = f"图片已生成: {revised_prompt}\n{result_text}"
                return result_text
            else:
                return "已调用绘图接口，但未接收到有效图片数据。"

        except openai.OpenAIError as e:
            logging.warning(f"调用 images.generate 绘图接口失败 ({e})，尝试回退到 chat.completions 对话接口")
            return self.talk(user_input)
        except Exception as e:
            logging.error(f"绘图处理发生异常: {e}")
            return f"绘图发生错误: {e}"

    def talk_draw(self, user_input):
        """
        支持绘画函数的别名
        """
        return self.draw(user_input)


# 测试代码
def main():
    parser = argparse.ArgumentParser(description="OpenAI 聊天客户端测试工具（支持多模态文件上传与图片生成保存）")
    parser.add_argument("--model", type=str, default="default", help="模型名称")
    parser.add_argument("--image-model", "--image_model", type=str, default="dall-e-3", help="图片生成模型名称 (默认: dall-e-3)")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:30000/v1", help="API基础 URL")
    parser.add_argument("--api_key", type=str, help="API 密钥 (如果未提供，将尝试从环境变量 OPENAI_API_KEY 获取)")
    parser.add_argument("--stream", action="store_true", help="是否启用流式响应")
    parser.add_argument("--draw", action="store_true", help="启用绘画模式 (单条提示词测试时使用)")
    parser.add_argument("--test-suite", "--test_suite", "--test", "-t", type=str, default="test_5_ping",
                        help=f"要执行的测试套件名称 (默认: test_5_ping，可选: {', '.join(test_suite.get_available_test_suites())})")
    parser.add_argument("--prompt", "-p", type=str, default=None, help="直接发送单条提示词（例如要求模型画一幅画），不指定则运行测试套件")
    parser.add_argument("--image", "--attachment", "-i", "-a", type=str, nargs="*", default=None, help="附加的本地文件路径列表（可指定多个）")
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
            stream=args.stream,
            image_model=args.image_model,
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
        stream=args.stream,
        image_model=args.image_model,
    )

    if args.prompt is not None:
        suite = test_suite.ChatContent()
        suite.allow_draw = bool(args.draw)
        suite.user_content = [
            {
                "message": args.prompt,
                "attachment_lists": args.image if args.image else [],
            }
        ]
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
        user_item = chat_content.get_validated_user_input(i)
        chat_content.add_messages({"role": "user", "content": user_item["message"]})
        reply = "dummy reply"  # 模拟模型的回复
        chat_content.add_messages({"role": "assistant", "content": reply})
    chat_content.save_chat_content()


if __name__ == "__main__":
    main()
    #test()
