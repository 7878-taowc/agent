from langchain_openai import ChatOpenAI

from settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# 统一的大模型实例
# temperature=0 保证 SQL 生成稳定，不引入随机性
llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    temperature=0,
)
