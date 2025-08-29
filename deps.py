# --------------------------------------
# deps - Модуль зависимостей FastAPI
# --------------------------------------

from fastapi import status, HTTPException
from fastapi import Security
from fastapi import Request, Depends, Response
from fastapi.responses import RedirectResponse
from fastapi.security import (
    APIKeyHeader, APIKeyCookie, APIKeyQuery,
    HTTPAuthorizationCredentials, HTTPBearer
)
from sqlmodel import select, update, delete
import logging

import models
import dbmgr
db = dbmgr.dbcm

#
# Аутентификация разными способами
# TODO: Cookie auth NOT worked - not income to cookie_api_key
#
HEADER_API_KEY = APIKeyHeader(name='X-API-KEY',auto_error=False)
COOKIE_API_KEY = APIKeyCookie(name='token', auto_error=False)
QUERY_API_KEY  = APIKeyQuery (name='token', auto_error=False)
SESSION_KEY    = APIKeyCookie(name='SESSION_ID', auto_error=False)
BEARER_API_KEY = HTTPBearer  (auto_error=False, description="Add the token to your bearer authentication")


class AuthUser(object):
    def __init__(self, user_id):
        self.user_id = user_id
        self.user    = None
        self.groups  = []
        self.rights  = []
        self.is_admin = False
        self.logged_in = False
        self.loaded = False

        self.get_from_db()


    def get_from_db(self):
        logging.error("get_from_db user '%s'..." % self.user_id)
        if not self.loaded and self.user_id:
            try:
                session = db.get_1_session()
                try:
                    db_user = session.exec(select(models.User).filter(models.User.uuid==self.user_id)).first()
                    if db_user:
                        self.user = db_user.dict()

                        self.groups = []
                        sql = select(models.Group, models.Membership).where(
                                     models.Membership.group == models.Group.uuid, 
                                     models.Membership.user  == self.user_id 
                              )
                        for group, membership in session.exec(sql).all():
                            if group.name == "Администраторы":
                                self.is_admin = True
                            self.groups.append(group.dict())

                        logging.info("get_from_db user '%s': user '%s' groups '%s'" % (self.user_id, self.user, self.groups))
                        self.loaded = True
                    else:
                        logging.error("get_from_db user '%s' not found!" % self.user_id)
                finally:
                    session.close()
            except:
                logging.exception("Ошибка загрузки данных пользователя '%s'" % self.user_id)
        return self.loaded


    def get_groups(self):
        return self.groups


    def get_user(self):
        return self.user


    def add_user_to_group_name(self, group_name):
        # check if user already in group
        if group_name and self.groups:
            for group in self.groups:
                if group["name"] == group_name:
                    return True

        res = False
        session = db.get_1_session()
        try:
            sql = select(models.Group).where(models.Group.name == group_name)
            db_group = session.exec(sql).first()
            logging.info("add_user_to_group_name '%s'" % db_group)
            if db_group:
                new_rec = self.create_object(session, models.Membership, dict(user=self.user_id, group=db_group.uuid))
                if new_rec:
                    self.groups.append(group.dict())
                    res = True
        finally:
            session.close()
        return res


    def create_object(self, session, obj_type, obj_dict):
        try:
            rec = obj_type(**obj_dict)
            session.add(rec)
            session.commit()
            session.refresh(rec)
            logging.info("created %s (%s) -> %s" % (obj_type, obj_dict, rec))
        except:
            rec = None
            logging.exception("create failed %s (%s)" % (obj_type, obj_dict))

        return rec


def check_api_key(
    request       : Request,
    header_api_key: str = Security(HEADER_API_KEY),
    cookie_api_key: str = Security(COOKIE_API_KEY),
    query_api_key : str = Security(QUERY_API_KEY ),
    session_key   : str = Security(SESSION_KEY   ),
    bearer_api_key: HTTPAuthorizationCredentials = Security(BEARER_API_KEY),
):
    logging.info("API Request %s %s" % (request.method, request.url))

    if bearer_api_key:
        bearer_key = bearer_api_key.credentials
    else:
        bearer_key = None
    
    logging.info(f"header : {header_api_key}")
    logging.info(f"cookie : {cookie_api_key}")
    logging.info(f"query  : {query_api_key }")
    logging.info(f"session: {session_key   }")
    logging.info(f"bearer : {bearer_key    }")
                    
    key = ""
    if header_api_key:  key = header_api_key
    if cookie_api_key:  key = cookie_api_key
    if query_api_key :  key = query_api_key 
    if session_key   :  key = session_key   
    if bearer_api_key:  key = bearer_api_key
    logging.info("key=%s" % key)

    # Внутренний проект - без проверки ключей
    # No key checking!!! Exists - ok.
    if key:
    #    key_info = await db.get_session_info(key)
    #    logging.info("key_info:", key_info)
        return {}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        #detail="Invalid API Key",
    )


def get_auth_user(request: Request):
    """verify that user has a valid session
       может также дополнять по user_id из базы user
    """
    user = None
    logging.info("Request %s %s" % (request.method, request.url))
    logging.info("In get_auth_user rcg=%s" % request.cookies.get("SESSION_ID"))
    session_id = request.cookies.get("SESSION_ID")
    logging.info("session_id=%s" % session_id)
    if session_id:
        session_info = db.get_session_info(session_id)
        logging.info("session_info: %s" % session_info)

        # Получить данные по user_id
        if session_info:
            user = AuthUser(session_info["userid"])
            if user.loaded:
                session_info["user"] = user
    else:
        session_info = None
    return session_info


