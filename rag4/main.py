import asyncio

from fastapi import FastAPI
from pydantic import BaseModel

from agent.sql_chain import ask_db

app = FastAPI(title="SQL 智能体")


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    sql: str
    result: str | None
    answer: str


@app.get("/")
def root():
    return {"message": "SQL 智能体已启动"}


@app.get("/tables")
def show_tables():
    """查看当前数据库有哪些表（调试用）"""
    from agent.sql_db import get_schema
    return {"schema": get_schema()}


@app.post("/ask", response_model=QueryResponse)
async def ask(req: QueryRequest):
    # ask_db 内部是同步 LLM 调用，放到线程池避免阻塞 FastAPI 事件循环
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ask_db, req.question)
