from langchain_community.utilities import SQLDatabase

from settings import DB_URI

# LangChain 的 SQLDatabase 走同步驱动，所以把 aiomysql 换回 pymysql
# 仅给 LangChain 用，不影响项目里异步的 SQLAlchemy
sync_uri = DB_URI.replace("+aiomysql", "+pymysql")

db = SQLDatabase.from_uri(sync_uri)


def get_schema() -> str:
    """返回所有表的结构（建表语句），喂给 LLM 让它知道有哪些字段"""
    return db.get_table_info()


def run_sql(sql: str) -> str:
    """执行 SQL 并返回结果字符串"""
    return str(db.run(sql))
