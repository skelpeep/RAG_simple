import dashscope
from http import HTTPStatus

from atguigu.config.config import RerankConfig

# 以下为华北2（北京）地域的配置，调用时请将{WorkspaceId}替换为真实的业务空间ID，各地域的配置不同。
dashscope.base_http_api_url = RerankConfig.rerank_base_url
dashscope.api_key = RerankConfig.rerank_api_key


def text_rerank(query,texts,limit=10):
    resp = dashscope.TextReRank.call(
        model="qwen3-rerank",
        query=query,
        documents=texts,
        top_n=limit,
        return_documents=False,  #
        instruct="Given a web search query, retrieve relevant passages that answer the query."
    )
    if resp.status_code == HTTPStatus.OK:
        # print(resp)
        return [
            {
                "index": item.index,
                "score": item.relevance_score
            }
            for item in resp.output.results
        ]
    else:
        print(resp)


if __name__ == '__main__':
    text_rerank()