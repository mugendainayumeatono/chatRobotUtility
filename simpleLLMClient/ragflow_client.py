import openai
import os
import logging

from ragflow_sdk import RAGFlow

import test_suite
from openAI_client import openaiClient

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s %(filename)s:%(lineno)d - %(message)s')

class ragflowClient(openaiClient):
    def __init__(self, model="default", temperature=0.7,url=""):
        super().__init__(model, temperature, url)
        self.api_key = "ragflow-cwZjJkMTRjMWY0NTExZjA5OGRiZmExZj"
        self.url = url

    def talk_init(self,test_suite):
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
    client = ragflowClient(model="default", url="http://js1.blockelite.cn:21666")
    client.run(test_suite.test_2())

if __name__ == "__main__":
    main()