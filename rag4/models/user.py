from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models import Base

# 密码加密器：使用 bcrypt 算法
password_hash = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    username: Mapped[str] = mapped_column(String(100))
    _password: Mapped[str] = mapped_column(String(200))

    def __init__(self, *args, **kwargs):
        # 把明文 password 从参数中取出，不传给父类（表里没有 password 列）
        password = kwargs.pop("password", None)
        super().__init__(*args, **kwargs)
        if password:
            # 走 setter，自动加密后存入 _password
            self.password = password

    @property
    def password(self):
        # 读取时返回的是加密后的密文
        return self._password

    @password.setter
    def password(self, raw_password):
        # 赋值时自动把明文加密
        self._password = password_hash.hash(raw_password)

    def check_password(self, raw_password):
        # 校验：明文 vs 密文
        return password_hash.verify(raw_password, self.password)


class EmailCode(Base):
    __tablename__ = "email_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(10))
    created_time: Mapped[datetime] = mapped_column(DateTime)
