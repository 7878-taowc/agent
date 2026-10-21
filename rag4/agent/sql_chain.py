import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import llm
from agent.sql_db import get_schema, run_sql

# ---------- 安全：只允许 SELECT，防止 DROP / DELETE 等危险操作 ----------
DANGEROUS_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter",
    "create", "truncate", "grant", "revoke",
]


def is_safe_sql(sql: str) -> bool:
    sql_lower = sql.lower()
    # 必须以 select 开头
    if not sql_lower.lstrip().startswith("select"):
        return False
    # 不能包含任何危险关键字
    for kw in DANGEROUS_KEYWORDS:
        if re.search(rf"\b{kw}\b", sql_lower):
            return False
    return True


# ---------- 第一步：让 LLM 根据表结构 + 问题生成 SQL ----------
sql_prompt = ChatPromptTemplate.from_template("""你是一个 MySQL 专家。根据下面的表结构，把用户的问题翻译成一条 SQL 查询语句。
要求：
1. 只返回 SQL 语句本身，不要有任何解释、markdown 代码块或多余文字。
2. 只能使用 SELECT 查询，不要写 INSERT / UPDATE / DELETE / DROP 等语句。
3. 如果问题无法用 SQL 回答，返回一句中文说明原因。

表结构：
{schema}

用户问题：{question}

SQL：""")

sql_chain = sql_prompt | llm | StrOutputParser()


# ---------- 第二步：让 LLM 把查询结果翻译成中文回答 ----------
answer_prompt = ChatPromptTemplate.from_template("""根据 SQL 查询结果，用中文简洁地回答用户的问题。
如果结果为空，就说"没有找到相关数据"。

用户问题：{question}
查询结果：{result}

回答：""")

answer_chain = answer_prompt | llm | StrOutputParser()


# ---------- 串联整个流程 ----------
def ask_db(question: str) -> dict:
    schema = get_schema()

    # 1. 生成 SQL
    raw_sql = sql_chain.invoke({"schema": schema, "question": question})
    # 清理可能的代码块符号和首尾空白
    sql = raw_sql.strip().strip("`").strip()

    # 2. 安全校验
    if not is_safe_sql(sql):
        return {
            "sql": sql,
            "result": None,
            "answer": "为了安全，只允许查询（SELECT）操作。",
        }

    # 3. 执行 SQL
    try:
        result = run_sql(sql)
    except Exception as e:
        return {
            "sql": sql,
            "result": None,
            "answer": f"SQL 执行出错：{str(e)[:200]}",
        }

    # 4. 翻译结果为中文
    answer = answer_chain.invoke({"question": question, "result": result})

    return {"sql": sql, "result": result, "answer": answer}
