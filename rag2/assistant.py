from dotenv import load_dotenv
from langchain.embeddings import init_embeddings
import os
from langchain_community.document_loaders import TextLoader
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_core.messages import AIMessageChunk, SystemMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from memory import LongTermMemory, UserInfo, EXTRACT_SYSTEM_PROMPT


MILVUS_URI = "http://localhost:19530"   # Milvus 服务的连接地址
DB_NAME = "rag_tutorial"                 # 自定义数据库名称
COLLECTION_NAME = "docs"                 # 向量集合名称（类似于传统数据库的表）
KNOWLEDGE_FILE = "./knowledge.txt"      # 本地知识库文件路径


EMBED_MODEL_NAME = "qwen3.7-text-embedding-flash"    # 嵌入模型名称
EMBED_DIM = 1024                        



from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymilvus import MilvusClient
from langchain.chat_models import init_chat_model
#初始化Milvus客户端
client = MilvusClient(MILVUS_URI)
# 查询已有的数据库，如果不存在指定名的数据库，则进行创建
existed_databases = client.list_databases()
if DB_NAME not in existed_databases:
    client.create_database(db_name=DB_NAME)
# 切换到指定的数据库
client.use_database(db_name=DB_NAME)


if client.has_collection(collection_name=COLLECTION_NAME):
    client.drop_collection(collection_name=COLLECTION_NAME)

client.create_collection(collection_name=COLLECTION_NAME, dimension=EMBED_DIM, metric_type="COSINE")



#初始化嵌入模型

load_dotenv(override=True)
embed_model = init_embeddings(
   model="openai:"+EMBED_MODEL_NAME,
   api_key=os.getenv("EMBED_MODEL_API_KEY"),
   base_url=os.getenv("EMBED_MODEL_API_URL"),
   dimensions=EMBED_DIM,
   check_embedding_ctx_length=False,
)


#切分知识库
loader = TextLoader(KNOWLEDGE_FILE, encoding="utf-8")
documents = loader.load()
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=80,
    separators=["\n\n", "\n", " "],
)
chunks = splitter.split_documents(documents)


# 从 Document 对象中提取 page_content 文本内容，转换为 embed_documents 所需的 list[str] 类型
texts = [chunk.page_content for chunk in chunks]
embeddings = embed_model.embed_documents(texts)

data = [
    {
        "id": i,
        "vector": embeddings[i],
        "text": texts[i],
        "source": KNOWLEDGE_FILE
    }
    for i in range(len(texts))

]
client.insert(collection_name=COLLECTION_NAME, data=data)



model = init_chat_model(
    model="openai:qwen3.8-flash",
    api_key=os.getenv("QWEN_API_KEY"),
    base_url=os.getenv("QWEN_API_URL"),
    temperature=0.5,
)

@tool
def search_knowledge(query: str) -> str:
    """在知识库中检索与问题相关的内容，返回最相关的文本片段"""
    query_embedding = embed_model.embed_query(query)
    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[query_embedding],
        limit=3,
        output_fields=["text"],
        search_params={"metric_type": "COSINE"},
    )
    return "\n---\n".join(hit["entity"]["text"] for hit in results[0])


checkpointer = InMemorySaver()

# 长期记忆：存用户偏好/个人信息到 PostgreSQL
long_memory = LongTermMemory()
USER_ID = "default_user"

# 把用户档案拼进 system prompt
profile_text = long_memory.to_prompt_text(USER_ID)
system_prompt = "你是一个专业的问答助手。回答用户问题前，必须先调用 search_knowledge 工具从知识库中检索相关内容，然后基于检索到的内容回答。如果知识库中没有相关信息，请直接说明。"
if profile_text:
    system_prompt += f"\n\n{profile_text}"

agent = create_agent(
    model=model,
    tools=[search_knowledge],
    checkpointer=checkpointer,
    system_prompt=system_prompt,
)

# 用同一个 thread_id 串联整个对话，InMemorySaver 据此共享多轮上下文
thread_config = {"configurable": {"thread_id": "conv_001"}}


#检索 + 生成回答（agent 自主调用检索工具）
while True:
    query = input("\n请输入你的问题（输入 q 退出）：")
    if query.strip() in ("q", "Q", "exit", "退出"):
        print("已退出。")
        break
    if not query.strip():
        continue

    # 1. 准备输入并调用 agent
    messages = [{"role": "user", "content": query}]
    stream = agent.stream(
        {"messages": [HumanMessage(content=query)]},
        config=cast("RunnableConfig", thread_config),
        stream_mode="messages",
    )

    # 2. 遍历流式结果并输出，同时累积完整回答
    print("\n助手回答：", end="", flush=True)
    full_answer = ""
    for chunk, _ in stream:
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            print(chunk.content, end="", flush=True)
            full_answer += chunk.content
    print()

    # 3. 从本轮对话提取用户信息并写入 PG
    conversation = f"用户：{query}\n助手：{full_answer}"
    extractor = model.with_structured_output(UserInfo)
    result = extractor.invoke([
        SystemMessage(content=EXTRACT_SYSTEM_PROMPT),
        HumanMessage(content=conversation),
    ])
    info = {k: v for k, v in result.model_dump().items() if v is not None and str(v).strip()}
    if info:
        long_memory.save_batch(USER_ID, info)
        print(f"[已提取用户信息] {info}")

