import openai
import os
import logging
import argparse

try:
    from ragflow_sdk import RAGFlow
except ImportError:
    RAGFlow = None

import test_suite
from openAI_client import openaiClient

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s %(filename)s:%(lineno)d - %(message)s')

class ragflowClient(openaiClient):
    support_attachments = False

    def __init__(self, model="default", temperature=0.7, url=""):
        super().__init__(model, temperature, url)
        self.api_key = "ragflow-cwZjJkMTRjMWY0NTExZjA5OGRiZmExZj"
        self.url = url

    def talk_init(self, test_suite):
        super().talk_init(test_suite)
        url = self.url
        #base_url="http://<YOUR_BASE_URL>:9380"
        #rag_object = RAGFlow(api_key=self.api_key, base_url=url)
        #datasets = rag_object.list_datasets(name="1_cfg")
        #dataset_ids = []
        #for dataset in datasets:
        #    dataset_ids.append(dataset.id)
        #dataset_ids = "69369fe21dfb11f09e822ab910408461"
        #assistant = rag_object.create_chat("default", dataset_ids=dataset_ids)

def main():
    parser = argparse.ArgumentParser(description="RAGFlow 聊天客户端测试工具")
    parser.add_argument("--model", type=str, default="default", help="模型名称")
    parser.add_argument("--url", type=str, default="http://js1.blockelite.cn:21666", help="RAGFlow 服务地址")
    parser.add_argument("--test-suite", "--test_suite", "--test", "-t", type=str, default="test_2",
                        help=f"要执行的测试套件名称 (默认: test_2，可选: {', '.join(test_suite.get_available_test_suites())})")
    parser.add_argument("--list-test", "--list-tests", "--list_tests", "--list_test", dest="list_test", action="store_true", help="列出所有可用的测试套件并退出")
    parser.add_argument("--list-modes", "--list-mode", "--list-models", "--list-model", "--list_modes", "--list_mode", dest="list_modes", action="store_true", help="列出全部可用的模型列表并退出")

    args = parser.parse_args()

    if args.list_test:
        print("可用的测试套件:")
        for name in test_suite.get_available_test_suites():
            print(f"  - {name}")
        return

    if args.list_modes:
        client = ragflowClient(model=args.model, url=args.url)
        models = client.list_models()
        if models:
            print(f"服务端 ({args.url}) 可用模型列表 (共 {len(models)} 个):")
            for m in models:
                print(f"  - {m}")
        else:
            print(f"未能获取到模型列表，请检查服务地址 ({args.url}) 是否正常运行及 API Key 是否有效。")
        return

    client = ragflowClient(model=args.model, url=args.url)
    try:
        suite = test_suite.get_test_suite(args.test_suite)
    except ValueError as e:
        logging.error(e)
        return

    client.run(suite)

if __name__ == "__main__":
    main()