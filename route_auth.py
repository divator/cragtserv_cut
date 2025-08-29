# --------------------------------------
# route_auth - Роутер авторизации
# --------------------------------------

from fastapi import APIRouter, status, HTTPException
from fastapi import Depends
from fastapi import Security, Depends, FastAPI, HTTPException, status, APIRouter, Response, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel import select, update, delete
from pydantic import UUID4

from typing import List
import logging

import models
import security
from deps import db, check_api_key, get_auth_user

router = APIRouter()

def append_text(fname, data, encoding="utf-8"):
    f = open(fname, "a+t", encoding=encoding)
    f.write(data)
    f.close()

DEF_PWD_LENGTH = 8


def user_has_permission(session, user_id, obj_tid, obj_id, perm_id):
    return True


@router.get("/whoami")
def auth_whoami(session_info = Depends(get_auth_user), session= Depends(db.get_session)) -> dict:
    logging.info("In auth_whoami %s" % session_info)
    if session_info:
        session_info["is_admin"] = session_info["user"].is_admin
        del session_info["user"]
        return session_info
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Forbidden"
        )


@router.post("/login")
def session_login(user: models.UserLogin):
    # если организация есть в списке баз клиентов:
    logging.info("Login: %s" % user)
    db_session = db.get_1_session()
    try:
        pwd_hash = security.make_pwd_hash(user.up)
        db_user = db_session.exec(select(models.User).filter(models.User.name==user.un)).first()
        if db_user and (db_user.pwd == pwd_hash):
            logging.info("User found: %s" % db_user)
            sess = models.Session(**dict(userid=db_user.uuid, stype=1, data=""))
            db_session.add(sess)
            db_session.commit()
            db_session.refresh(sess)
            logging.info("Session created: %s" % sess)

            response = HTMLResponse(content="OK")
            response.set_cookie(key="SESSION_ID", value=sess.uuid, expires=86400*365, max_age=86400*365)
            return response
        else:
            logging.info("User not found!")
            #repodb_session.commit()
    finally:
        db_session.close()

    raise HTTPException(status_code=404)


@router.post("/logout")
@router.get("/logout")
def session_logout(request: Request):
    logging.info("logout")
    session_id = request.cookies.get("SESSION_ID")
    logging.info("logout session: %s" % session_id)
    if session_id:
        db_session = db.get_1_session()
        try:
            sess = db_session.get(models.Session, session_id)
            if not sess:
                logging.info("logout session '%s' not found" % session_id)
                db_session.commit()
                raise HTTPException(status_code=404, detail="Session not found")
            db_session.delete(sess)
            db_session.commit()
            logging.info("logout session '%s' deleted" % session_id)
        except:
            logging.exception("Exception in logout session")
        finally:
            db_session.close()
        
    response = Response(status_code=status.HTTP_202_ACCEPTED)
    response.delete_cookie(key="SESSION_ID")
    logging.info("logout session '%s' cleared" % session_id)
    return response


def create_user(session, user):
    # generate random password
    pwd = security.gen_random_pwd(DEF_PWD_LENGTH)
    pwd_hash = security.make_pwd_hash(pwd)
    append_text("defpwds.txt", "%s %s\n" % (pwd, user))

    # create user
    new_user = models.User(**user.dict())
    new_user.pwd = pwd_hash
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    # create user group
    new_group = models.Group(name="user_%s" % new_user.uuid)
    session.add(new_group)
    session.commit()
    session.refresh(new_group)

    # create user group membership
    new_member = models.Membership(group=new_group, user=new_user)
    session.add(new_group)
    session.commit()

    return {"name":new_user.name, "uuid":new_user.uuid}


@router.post("/user/add", dependencies=[Depends(check_api_key)])
def add_user(user: models.UserCreate, session_info = Depends(get_auth_user), session= Depends(db.get_session)):
    logging.info("In add_user '%s' by '%s'" % (user, session_info))
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Forbidden"
        )

    if not user_has_permission(session, session_info["userid"], "table", "auth_user", "create"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Forbidden"
        )
    
    res = {}
    try:
        res = create_user(session, user)
        logging.info("add_user: %s" % res)
    except:
        logging.exception("Ошибка в add_user")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return res
