# --------------------------------------
# route_auth - Роутер метаданных
# --------------------------------------

from sqlalchemy.orm import Session

from fastapi import APIRouter, status, HTTPException
from fastapi import Depends
from fastapi import Security, Depends, FastAPI, HTTPException, status, APIRouter, Response, Query, Request

from sqlmodel import select, update, delete

from typing import List
import logging

from deps import db, check_api_key, get_auth_user
import models

router = APIRouter()


USR_SDT_FMT = "%d.%m.%y %H:%M:%S"


@router.get("/tables", dependencies=[Depends(check_api_key)])
def get_tables(response: Response, offset: int = 0, limit: int = Query(default=100, le=100), session = Depends(db.get_session)):
    tables = []
    try:
        tables = [
            {"id":"orgs_id", "name":"orgs"},
            {"id":"user_id", "name":"user"},
            {"id":"auth_id", "name":"auth"},
        ]
        # This is necessary for react-admin to work
        response.headers["Content-Range"] = f"0-9/{len(orgs)}"
    except:
        logging.exception("Ошибка в tables")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return tables


@router.post("/tables", dependencies=[Depends(check_api_key)])
def add_table(table:str, session = Depends(db.get_session)):
    logging.info("add_table: %s" % table)
    try:
        logging.info("Table created: %s" % table)
    except:
        logging.exception("Ошибка в add_table")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return new_org.uuid


@router.delete("/tables/{name}", dependencies=[Depends(check_api_key)])
def del_table(name, session = Depends(db.get_session)):
    logging.info("del_table: %s" % name)
    try:
        logging.info("Table deleted")
    except:
        logging.exception("Ошибка в del_table")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return {"result":"OK"}

