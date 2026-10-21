"""
长期记忆模块：用 PostgreSQL 存储用户偏好/个人信息
"""
import os
os.environ["PGCLIENTENCODING"] = "UTF8"  # 必须在 psycopg2 连接前设置，避免 Windows GBK 解码错误

from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv(override=True)
Base = declarative_base()

# ======================== 配置 ========================
PG_URI = os.getenv("PG_URI")
PROFILE_TABLE = os.getenv("PROFILE_TABLE", "user_profiles")

# ======================== 表结构 ========================
class UserProfile(Base):
    """用户长期信息表，每条记录是一个键值对"""
    __tablename__ = os.getenv("PROFILE_TABLE")

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)   # 用户标识
    key = Column(String(128), nullable=False)                  # 信息类型：name/age/hobby...
    value = Column(Text, nullable=False)                       # 信息内容
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ======================== 长期记忆读写类 ========================
class LongTermMemory:
    def __init__(self, pg_uri: str | None = os.getenv("PG_URI")):
        if pg_uri is None:
            raise ValueError("PG_URI 环境变量未设置")
        self.engine = create_engine(pg_uri, echo=False)
        Base.metadata.create_all(self.engine)   # 自动建表
        self.Session = sessionmaker(bind=self.engine)

    def save(self, user_id: str, key: str, value: str):
        """保存/更新一条信息，同 user_id + key 已存在则覆盖"""
        with self.Session() as session:
            existing = session.query(UserProfile).filter_by(
                user_id=user_id, key=key
            ).first()
            if existing:
                existing.value = value  # type: ignore[assignment]
            else:
                session.add(UserProfile(user_id=user_id, key=key, value=value))
            session.commit()

    def save_batch(self, user_id: str, info_dict: dict):
        """批量保存多条信息"""
        for key, value in info_dict.items():
            if value:
                self.save(user_id, key, str(value))

    def get_all(self, user_id: str) -> dict:
        """获取该用户所有信息，返回 {key: value}"""
        with self.Session() as session:
            rows = session.query(UserProfile).filter_by(user_id=user_id).all()
            return {r.key: r.value for r in rows}

    def to_prompt_text(self, user_id: str) -> str:
        """格式化成 system prompt 片段"""
        profile = self.get_all(user_id)
        if not profile:
            return ""
        lines = [f"- {k}: {v}" for k, v in profile.items()]
        return "【用户档案】\n" + "\n".join(lines)
    


# ======================== 结构化输出 Schema ========================
from typing import Optional
from pydantic import BaseModel, Field

class UserInfo(BaseModel):
    """从对话中提取的用户个人信息，无信息时字段留空"""
    name: Optional[str] = Field(default=None, description="用户的姓名")
    age: Optional[str] = Field(default=None, description="用户的年龄")
    gender: Optional[str] = Field(default=None, description="用户的性别")
    hobby: Optional[str] = Field(default=None, description="用户的爱好或兴趣")
    preference: Optional[str] = Field(default=None, description="用户的偏好或喜欢的事物")
    dislike: Optional[str] = Field(default=None, description="用户不喜欢的事物")
    job: Optional[str] = Field(default=None, description="用户的职业")
    location: Optional[str] = Field(default=None, description="用户的所在地")
    custom: Optional[str] = Field(default=None, description="其他值得记录的用户信息")

EXTRACT_SYSTEM_PROMPT = """你是一个用户信息抽取助手。
从对话中提取用户的个人信息或偏好，只提取陈述句中明确表达的信息，忽略疑问句和指令句。
没有相关信息的字段保持为空。"""


