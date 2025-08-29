# --------------------------------------
# models - Описание моделей объектов
# --------------------------------------

from typing import Optional, List
import uuid as uuid_pkg
from datetime import datetime

from pydantic import UUID4, BaseModel
from sqlalchemy import text, UniqueConstraint
from sqlalchemy.orm import registry

from sqlmodel import Field, SQLModel
from sqlmodel import Relationship


class HealthCheck(BaseModel):
    name: str
    version: str
    description: str


class StatusMessage(BaseModel):
    status: bool
    message: str


class UUIDModel(SQLModel):
    uuid: UUID4 = Field(default_factory=uuid_pkg.uuid4, primary_key=True)


class TimestampModel(SQLModel):
    cdt: datetime = Field(default_factory=datetime.utcnow)


#
# === Agents ===
#
class AgentBase(SQLModel):
    name     : str = ""  # Человеческое имя "Магазин ХХХ, касса 1"
    iname    : str = ""  # "Внутреннее" имя "UVAT_SEVER_KASSA1"
    hostname : str = ""  # WIN-GTXC268763
    agt_qname: str = ""  # uvat.sever1.kassa1
    active   : bool = False
    lic      : UUID4 = Field(foreign_key="lics.uuid")

class Agent(UUIDModel, AgentBase, TimestampModel, table=True):
    __tablename__ = "agents"


#
# === Lics ===
#
class LicBase(SQLModel):
    name     : str = ""  # Человеческое имя "Лицензия на 25 агентов"
    #sdt      : datetime.date = Field(default_factory=datetime.today) # начало срока действия
    #edt      : datetime.date = Field(default_factory=datetime.today) # конец  срока действия
    sdt      : datetime = Field(default_factory=datetime.utcnow) # начало срока действия
    edt      : datetime = Field(default_factory=datetime.utcnow) # конец  срока действия
    org_inn  : str = "" 
    org_name : str = "" 
    agt_count: int = 0
    active   : bool = False
    ltype    : int = 0 # 0 - demo, 1 - evaluation, 2 - commerce

class Lic(UUIDModel, LicBase, TimestampModel, table=True):
    __tablename__ = "lics"


#
# === Logins ===
#
class LoginBase(SQLModel):
    agent    : UUID4 = Field(foreign_key="agents.uuid")
    ltype    : int = 0     # 0 - unknown, 1 - login, 2 - logout, 3 - other event
    req      : str = ""    # Данные запроса авторизации
    rsp      : str = ""    # Данные результата авторизации
    success  : bool = True # Данные результата авторизации

class Login(UUIDModel, LoginBase, TimestampModel, table=True):
    __tablename__ = "logins"


#
# === User ===
#
class UserBase(SQLModel):
    name  : str
    pwd   : str
    email : str
    phone : str = ""
    telegram : str = ""


class User(UUIDModel, UserBase, TimestampModel, table=True):
    __tablename__ = "users"
    #__table_args__ = (
    #    UniqueConstraint('name' , name='uc_name'),
    #    UniqueConstraint('email', name='uc_email'),
    #)


class UserCreate(BaseModel):
    name  : str
    email : str
    telegram : str = ""


class UserLogin(BaseModel):
    un : str
    up : str

#
# === Group ===
#
class GroupBase(SQLModel):
    name  : str


class Group(UUIDModel, GroupBase, TimestampModel, table=True):
    __tablename__ = "groups"


#
# === Membership ===
#
class MembershipBase(SQLModel):
    user  : UUID4 = Field(default=None, foreign_key="users.uuid")
    group : UUID4 = Field(default=None, foreign_key="groups.uuid")


class Membership(UUIDModel, MembershipBase, TimestampModel, table=True):
    __tablename__ = "memberships"



#
# === Session ===
#
class SessionBase(SQLModel):
    userid : UUID4
    stype  : int = 1     # 1 - browser session, 2 - API Key
    data   : str = None  # session data

class Session(UUIDModel, SessionBase, TimestampModel, table=True):
    __tablename__ = "sessions"


