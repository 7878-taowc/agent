from sqlalchemy import  MetaData
from sqlalchemy.orm import  DeclarativeBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from settings import DB_URI

# 数据库引擎
engine = create_async_engine(
    DB_URI,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,   # 异步下建议开启
)

# 定义命名约定的 Base 类
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        # ix: index，索引
        "ix": "ix_%(column_0_label)s",
        # uq: unique，唯一约束
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        # ck: Check，检查约束
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        # fk: Foreign Key，外键约束
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        # pk: Primary Key，主键约束
        "pk": "pk_%(table_name)s",
    })

from . import user  # noqa: F401  导入该模块即完成 User / EmailCode 向 Base.metadata 的注册