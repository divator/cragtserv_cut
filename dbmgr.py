# --------------------------------------
# db - Модуль работы с СУБД
# --------------------------------------

import os
import logging
import datetime
from typing import Generator

from sqlmodel import SQLModel, create_engine, Session, MetaData
from sqlmodel import select, update, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

import models
import security

class DbConnMgr(object):
    def __init__(self, conn_str, params):
        self.conn_str = conn_str
        self.params = params

        self.engine = None
        self.created = False
        self.metadata = None

        try:
            if "sqlite" in conn_str:
                #self.engine = create_engine(conn_str, echo=True, future=True, connect_args={"check_same_thread": False})
                self.engine = create_engine(conn_str, future=True, connect_args={"check_same_thread": False})
            else:
                #self.engine = create_engine(conn_str, echo=True, future=True)
                self.engine = create_engine(conn_str, future=True)

            self.created = True
        except:
            logging.exception("Cannot create DB engine name=%s, conn_str=%s, param=%s" % (name, conn_str, params))


    def reflect(self):
        if not self.engine:
            return None

        if not self.metadata:
            self.metadata = MetaData(self.engine)
            self.metadata.reflect(bind=self.engine)
        return self.metadata


    def init_db(self):
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine) as session:
            db_user = session.exec(select(models.User).filter(models.User.name=="admin")).first()
            if not db_user:
                logging.info("User admin NOT found! Create...")
                admin = models.User(**dict(name="admin", pwd=security.make_pwd_hash("admin"), email="admin@admin.com"))
                session.add(admin)
                session.commit()
                session.refresh(admin)
                logging.info("Admin created: %s" % admin)


    def get_session_info(self, session_id):
        session_info = None
        with Session(self.engine) as session:
            sess = session.exec(select(models.Session).filter(models.Session.uuid==session_id)).first() #.offset(offset).limit(limit)
            if sess:
                session_info = sess.dict()
                session_info["org_title"] = "Неизвестная организация"

        logging.info("get_session_info: %s, %s" % (session_id, session_info))
        return session_info


    def get_user_info(self, userid):
        user = None
        with self.get_1_session() as session:
            user = session.exec(select(models.User).filter(models.User.uuid==userid)).first() #.offset(offset).limit(limit)
            if user:
                user = user.dict()
        logging.info("get_user_info: %s -> %s" % (userid, user))
        return user


    def drop_db(self):
        SQLModel.metadata.drop_all(self.engine)


    def get_session(self) -> Generator:
        engine = self.engine
        with Session(engine) as session:
            yield session


    def get_1_session(self):
        return Session(self.engine)


    def get_obj_list(self, model): 
        """ model - модель для таблицы
        """
        recs = []
        session = self.get_1_session()
        with self.get_1_session() as session:
            recs = session.exec(select(model)).all()
        return recs


    def get_obj_by_id(self, model, uuid): 
        """ model - модель для таблицы
            uuid  - Идентификатор записи
        """
        obj = None
        with self.get_1_session() as session:
            obj = session.get(model, uuid)
        return obj


    def add_obj(self, model, base, obj): 
        """ model - модель для таблицы
            base  - Pydantic модель для сущности
            obj   - Объект в виде словаря
            Pydantic нужен для валидации структуры сущности
        """
        new_rec = None
        with self.get_1_session() as session:
            new_rec = model(**base(**obj).dict())
            session.add(new_rec)
            session.commit()
            session.refresh(new_rec)
        return new_rec


    def del_obj(self, model, uuid): 
        """ model - модель для таблицы
            uuid  - Идентификатор записи
        """
        res = False
        with self.get_1_session() as session:
            obj = session.get(model, uuid)
            if obj:
                session.delete(obj)
                session.commit()
                res = True
        return res


    def upd_obj(self, model, base, uuid, obj): 
        """ model - модель для таблицы
            base  - Pydantic модель для сущности
            obj   - Объект в виде словаря
            Pydantic нужен для валидации структуры сущности
        """
        upd_obj = None
        with self.get_1_session() as session:
            db_obj = session.get(model, uuid)
            if not db_obj:
                return db_obj
            
            for key, value in base(**obj).dict().items():
                setattr(db_obj, key, value)
                
            upd_obj = db_obj.dict()
            session.add(db_obj)
            session.commit()
        return upd_obj


    def bl_is_lic_valid(self, lic): 
        now = datetime.datetime.now()
        valid = lic and lic.active and (lic.sdt <= now) and (now <= lic.edt)
        return valid


    def bl_is_agent_can_work(self, lic_id, agt_id): 
        lic = db.get_obj_by_id(models.Lic  , lic_id)
        agt = db.get_obj_by_id(models.Agent, agt_id)
        can_work = agt and self.bl_is_lic_valid(lic) and agt.active
        return can_work


    def bl_lic_agent_cnt(self, lic_id): 
        cur_agt_cnt = None
        with self.get_1_session() as session:
            cur_agt_cnt = session.exec(
                select(func.count(models.Agent.uuid)).filter(
                    models.Agent.lic == lic_id
                )
            ).one()
        return cur_agt_cnt
    

    def bl_reg_agent(self, lic_id, hname): 
        lic = self.get_obj_by_id(models.Lic  , lic_id)
        if self.bl_is_lic_valid(lic):
            max_agt_cnt = lic.agt_count
            logging.info("В лицензии %s агентов %d." % (lic_id, max_agt_cnt))
            cur_agt_cnt = self.bl_lic_agent_cnt(lic_id)
            logging.info("В лицензии %s агентов %s/%s." % (lic_id, cur_agt_cnt, max_agt_cnt))
            if cur_agt_cnt < max_agt_cnt:
                agent = {
                    "name"     : "%s_%s" % (lic.org_inn, hname), # Человеческое имя
                    "iname"    : "%s_%s" % (lic.org_inn, hname), # "Внутреннее" имя
                    "hostname" : hname,  # WIN-GTXC268763
                    "active"   : True,
                    "lic"      : lic.uuid,
                }
                new_agent = self.add_obj(models.Agent, models.AgentBase, agent)
                new_agent.agt_qname = str(new_agent.uuid)
                new_agent = self.upd_obj(models.Agent, models.AgentBase, new_agent.uuid, new_agent.dict())
                res = {"error":"", "data":new_agent}
                logging.info("В лицензию %s добавлен агент. Теперь %d/%d агентов." % (lic_id, cur_agt_cnt+1, max_agt_cnt))
            else:
                res = {"error":"Все агентские лицензии использованы"}
        else:
            res = {"error":"Лицензия недействительна"}
        return res


#
# Database setup
#
#DATABASE_URL = os.environ.get("DATABASE_URL")
#DATABASE_URL = "sqlite+aiosqlite:///./crmon.db"
DATABASE_URL = "sqlite:///./cragtsrv.db"
dbcm = DbConnMgr(DATABASE_URL, {})
print("manager created")
