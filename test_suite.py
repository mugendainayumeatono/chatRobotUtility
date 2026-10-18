import base64
import binascii
import datetime
import hashlib
import inspect
import logging
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, List, Optional, Tuple

MAX_IMAGE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB max image size

MIME_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}


def get_log_dir(log_dir: Optional[ Any ] = None) -> Path:
    """
    获取并确保 logs 目录存在
    """
    if log_dir is None:
        dir_path = Path(__file__).resolve().parent / "logs"
    else:
        dir_path = Path(log_dir).resolve()
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def detect_image_extension(image_bytes: bytes, mime_type: Optional[str] = None) -> Optional[str]:
    """
    通过文件魔数（Magic Bytes）检测并验证图片格式扩展名
    返回：
        合法图片的扩展名（如 '.png', '.jpg'），若非支持的图片格式则返回 None
    """
    if not isinstance(image_bytes, (bytes, bytearray)) or len(image_bytes) < 4:
        return None

    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(image_bytes) >= 12 and image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return ".webp"
    if image_bytes.startswith(b"BM"):
        return ".bmp"

    if mime_type:
        normalized_mime = mime_type.split(";")[0].strip().lower()
        if normalized_mime in MIME_TO_EXT:
            return MIME_TO_EXT[normalized_mime]

    return None


def detect_image_mime(image_bytes: bytes, fallback: str = "image/png") -> str:
    """
    根据图片字节流推断 MIME 类型
    """
    ext = detect_image_extension(image_bytes)
    ext_to_mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return ext_to_mime.get(ext, fallback)


def save_image_bytes(
    image_bytes: bytes,
    mime_type: Optional[str] = None,
    log_dir: Optional[Any] = None,
    prefix: str = "image",
) -> Optional[Path]:
    """
    将图片字节流保存到 logs 文件夹中
    参数：
        image_bytes: 图片二进制数据
        mime_type: 可选的 MIME 类型
        log_dir: 保存目录（默认为项目根目录下的 logs 文件夹）
        prefix: 文件名前缀（默认 'image'）
    返回：
        保存成功后的本地文件路径 Path，失败则返回 None
    """
    if not image_bytes:
        logging.error("保存图片失败: 图片数据为空")
        return None

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        logging.error(f"保存图片失败: 图片大小超过限制 ({MAX_IMAGE_SIZE_BYTES} bytes)")
        return None

    ext = detect_image_extension(image_bytes, mime_type)
    if ext is None:
        logging.error("保存图片失败: 未识别或不支持的图片格式")
        return None

    dir_path = get_log_dir(log_dir).resolve()
    safe_prefix = re.sub(r"[^a-zA-Z0-9_-]", "", os.path.basename(prefix)) or "image"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    candidate_name = f"{safe_prefix}_{timestamp}{ext}"
    file_path = (dir_path / candidate_name).resolve()
    counter = 1
    while file_path.exists():
        candidate_name = f"{safe_prefix}_{timestamp}_{counter}{ext}"
        file_path = (dir_path / candidate_name).resolve()
        counter += 1

    # 路径边界安全校验，防止目录穿越
    if not str(file_path).startswith(str(dir_path) + os.sep):
        logging.error("保存图片失败: 非法的目标文件路径")
        return None

    with file_path.open("wb") as f:
        f.write(image_bytes)

    logging.info(f"图片已保存到 {file_path}")
    return file_path


def decode_data_uri(data_uri: str) -> Optional[Tuple[bytes, str]]:
    """
    解析 data:image/...;base64,... 格式的字符串
    返回：
        (image_bytes, mime_type) 或 None
    """
    if not isinstance(data_uri, str) or not data_uri.startswith("data:"):
        return None

    match = re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data_uri.strip(), re.DOTALL)
    if not match:
        return None

    mime_type = (match.group(1) or "image/png").strip()
    is_base64 = bool(match.group(2))
    raw_data = match.group(3).strip()

    try:
        if is_base64:
            cleaned = re.sub(r"\s+", "", raw_data)
            if len(cleaned) > (MAX_IMAGE_SIZE_BYTES * 4 // 3) + 1024:
                logging.error("数据大小超过上限，拒绝解码 base64 图片")
                return None
            image_bytes = base64.b64decode(cleaned, validate=False)
        else:
            image_bytes = urllib.parse.unquote_to_bytes(raw_data)
        return image_bytes, mime_type
    except (ValueError, TypeError, binascii.Error) as e:
        logging.error(f"解析 data URI 失败: {e}")
        return None


def fetch_image_from_url(url: str, timeout: int = 30) -> Optional[Tuple[bytes, Optional[str]]]:
    """
    从 HTTP/HTTPS URL 下载图片字节数据
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logging.error(f"不支持的图片 URL 协议: {parsed.scheme}")
        return None

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SimpleLLMClient/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type")
            data = resp.read(MAX_IMAGE_SIZE_BYTES + 1)
            if len(data) > MAX_IMAGE_SIZE_BYTES:
                logging.error("下载图片失败: 远程文件大小超过上限")
                return None
            return data, content_type
    except Exception as e:
        logging.error(f"从 URL 下载图片失败 ({url}): {e}")
        return None


def extract_image_bytes_from_source(
    source: Any,
    mime_type: Optional[str] = None,
) -> Optional[Tuple[bytes, Optional[str]]]:
    """
    从模型返回的各种图片结构（dict、对象、data URI、URL、base64）中提取 (image_bytes, mime_type)
    """
    if source is None:
        return None

    if isinstance(source, (bytes, bytearray)):
        return bytes(source), mime_type

    if hasattr(source, "model_dump"):
        source = source.model_dump()
    elif not isinstance(source, (dict, str)) and hasattr(source, "__dict__"):
        source = vars(source)

    if isinstance(source, dict):
        # 1. 处理 {"type": "image_url", "image_url": {"url": "..."}} 或 {"image_url": "..."}
        if "image_url" in source and source["image_url"] is not None:
            img_url_obj = source["image_url"]
            if isinstance(img_url_obj, dict):
                url = img_url_obj.get("url")
                mime = img_url_obj.get("mime_type") or source.get("mime_type") or mime_type
                return extract_image_bytes_from_source(url, mime)
            elif isinstance(img_url_obj, str):
                return extract_image_bytes_from_source(img_url_obj, source.get("mime_type") or mime_type)

        # 2. 处理 {"inline_data": {"mime_type": "...", "data": "..."}} 或 {"inlineData": ...}
        inline_data = source.get("inline_data") or source.get("inlineData")
        if isinstance(inline_data, dict):
            b64_data = inline_data.get("data")
            mime = inline_data.get("mime_type") or inline_data.get("mimeType") or mime_type
            if isinstance(b64_data, str) and b64_data:
                return extract_image_bytes_from_source(b64_data, mime)

        # 3. 处理 {"b64_json": "..."} 或 {"data": "..."} 或 {"base64": "..."}
        for key in ("b64_json", "data", "base64", "partial_image_b64", "result"):
            val = source.get(key)
            if isinstance(val, str) and val:
                fmt = source.get("output_format")
                inferred_mime = f"image/{fmt}" if fmt else (source.get("mime_type") or source.get("media_type") or mime_type)
                return extract_image_bytes_from_source(val, inferred_mime)

        # 4. 处理 {"url": "..."}
        if isinstance(source.get("url"), str) and source["url"]:
            return extract_image_bytes_from_source(source["url"], source.get("mime_type") or mime_type)

        return None

    if isinstance(source, str):
        s = source.strip()
        if not s:
            return None
        if s.startswith("data:"):
            return decode_data_uri(s)
        if s.startswith(("http://", "https://")):
            return fetch_image_from_url(s)
        # 尝试作为纯 base64 字符串解码
        try:
            cleaned = re.sub(r"\s+", "", s)
            if len(cleaned) > (MAX_IMAGE_SIZE_BYTES * 4 // 3) + 1024:
                return None
            raw_bytes = base64.b64decode(cleaned, validate=False)
            if detect_image_extension(raw_bytes, mime_type) is not None:
                return raw_bytes, mime_type
        except Exception:
            pass

    return None


def save_image_from_source(
    source: Any,
    mime_type: Optional[str] = None,
    log_dir: Optional[Any] = None,
    prefix: str = "image",
) -> Optional[Path]:
    """
    从图片数据源中提取图片并保存至 logs 目录
    """
    extracted = extract_image_bytes_from_source(source, mime_type)
    if not extracted:
        return None
    image_bytes, detected_mime = extracted
    return save_image_bytes(image_bytes, detected_mime or mime_type, log_dir=log_dir, prefix=prefix)


def extract_and_save_images_from_text(
    text: str,
    log_dir: Optional[Any] = None,
    seen_hashes: Optional[set] = None,
) -> Tuple[str, List[Path]]:
    """
    从文本回复中提取内嵌的图片（如 Markdown data:image/... 或 https:// 图片链接、裸 data:image/...），
    将其保存至 logs 文件夹，并将超长 base64 替换为本地文件路径说明。
    返回：
        (清理后的文本, 保存的图片路径列表)
    """
    if not isinstance(text, str) or not text:
        return text, []

    saved_paths: List[Path] = []
    if seen_hashes is None:
        seen_hashes = set()

    def _save_unique(img_bytes: bytes, mime: Optional[str]) -> Optional[Path]:
        digest = hashlib.sha256(img_bytes).hexdigest()
        if digest in seen_hashes:
            return None
        path = save_image_bytes(img_bytes, mime, log_dir=log_dir)
        if path is not None:
            seen_hashes.add(digest)
            saved_paths.append(path)
        return path

    # 1. 匹配 Markdown 格式的 data URI 图片: ![alt](data:image/...;base64,...)
    md_data_pattern = re.compile(r"!\[([^\]]*)\]\((data:image/[^)]+)\)", re.DOTALL)

    def _replace_md_data(match: re.Match) -> str:
        alt = match.group(1)
        data_uri = match.group(2)
        decoded = decode_data_uri(data_uri)
        if decoded:
            img_bytes, mime = decoded
            path = _save_unique(img_bytes, mime)
            if path is not None:
                return f"![{alt}]({path})"
        return match.group(0)

    cleaned_text = md_data_pattern.sub(_replace_md_data, text)

    # 2. 匹配文本中裸露的 data:image/...;base64,...
    raw_data_pattern = re.compile(
        r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+",
    )

    def _replace_raw_data(match: re.Match) -> str:
        data_uri = match.group(0)
        decoded = decode_data_uri(data_uri)
        if decoded:
            img_bytes, mime = decoded
            path = _save_unique(img_bytes, mime)
            if path is not None:
                return f"[图片已保存至: {path}]"
        return match.group(0)

    cleaned_text = raw_data_pattern.sub(_replace_raw_data, cleaned_text)

    # 3. 匹配 Markdown 格式的远程图片链接: ![alt](https://...)
    md_url_pattern = re.compile(r"!\[([^\]]*)\]\((https?://[^\s)]+)\)")

    def _replace_md_url(match: re.Match) -> str:
        alt = match.group(1)
        url = match.group(2)
        fetched = fetch_image_from_url(url)
        if fetched:
            img_bytes, mime = fetched
            if detect_image_extension(img_bytes, mime) is not None:
                path = _save_unique(img_bytes, mime)
                if path is not None:
                    return f"![{alt}]({url}) [图片已保存至: {path}]"
        return match.group(0)

    cleaned_text = md_url_pattern.sub(_replace_md_url, cleaned_text)

    return cleaned_text, saved_paths


class ChatContent:
    system_content = ""
    user_content = []

    def __init__(self, log_dir=None):
        self.messages = []
        self.saved_images: List[Path] = []
        self.log_dir = log_dir

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
        if not isinstance(text, str):
            return text
        # 查找 </think> 的位置
        index = text.find("</think>")
        if index != -1:  # 如果找到了 </think>
            # 返回 </think> 及其之后的内容
            return text[index + 8:]
        else:
            # 如果没找到，返回原字符串
            return text

    def save_image(self, source: Any, mime_type: Optional[str] = None, log_dir: Optional[Any] = None) -> Optional[Path]:
        """
        保存模型返回的图片到 logs 文件夹，并记录到当前会话的 saved_images 列表中
        """
        target_dir = log_dir if log_dir is not None else self.log_dir
        path = save_image_from_source(source, mime_type=mime_type, log_dir=target_dir)
        if path is not None:
            self.saved_images.append(path)
        return path

    def add_messages(self, input, is_with_think=False):
        """
        记录聊天内容
        参数：
            input: 消息字典（包含 role 和 content）
        """
        if isinstance(input, dict):
            content = input.get("content", "")
            if not is_with_think and isinstance(content, str):
                content = self.truncate_before_think(content)

            # 若 assistant 回复中包含内联图片数据，自动提取并保存到 logs 文件夹
            if input.get("role") == "assistant" and isinstance(content, str) and "data:image/" in content:
                content, paths = extract_and_save_images_from_text(content, log_dir=self.log_dir)
                self.saved_images.extend(paths)

            input["content"] = content

        self.messages.append(input)
        self.format_output(input)

    def save_chat_content(self, log_dir=None):
        """
        保存聊天内容到文件
        """
        # 获取当前日期时间
        current_time = datetime.datetime.now()
        # 格式化为字符串（例如：20250406_143022）
        filename = current_time.strftime("chat_log_%Y%m%d_%H%M%S") + ".log"
        target_dir = log_dir if log_dir is not None else self.log_dir
        dir_path = get_log_dir(target_dir)
        file_path = dir_path / filename
        with file_path.open("w", encoding="utf-8") as f:
            for content in self.messages:
                f.write(str(content).replace("\\n", "\n") + "\n")
        logging.info(f"聊天内容已保存到 {file_path}")
        return file_path


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


class test_5_ping(ChatContent):
    user_content = [
        "你是谁，什么版本",
    ]


class test_6_draw(ChatContent):
    user_content = [
        "请画一幅画：一只戴着宇航员头盔的可爱橘猫在月球上散步，背景是璀璨的星空和蔚蓝的地球。",
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


def get_available_test_suites():
    """
    获取所有已定义的测试套件名称列表
    """
    current_module = sys.modules[__name__]
    suites = []
    for name, cls in inspect.getmembers(current_module, inspect.isclass):
        if issubclass(cls, ChatContent) and cls is not ChatContent:
            suites.append(name)
    return sorted(suites)


def get_test_suite(name: str, *args, **kwargs) -> ChatContent:
    """
    根据测试套件名称获取其实例
    参数：
        name: 测试套件类名（例如 'test_1', 'test_5_ping', 'test_6_draw'）
    返回：
        ChatContent 测试套件实例
    异常：
        ValueError: 当未找到对应测试套件时抛出
    """
    current_module = sys.modules[__name__]
    cls = getattr(current_module, name, None)
    if cls is not None and inspect.isclass(cls) and issubclass(cls, ChatContent) and cls is not ChatContent:
        return cls(*args, **kwargs)

    available = get_available_test_suites()
    raise ValueError(f"未找到测试套件 '{name}'。可用测试套件列表: {', '.join(available)}")


