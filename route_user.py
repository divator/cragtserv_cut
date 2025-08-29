# --------------------------------------
# route_auth - Роутер таблиц
# --------------------------------------

from sqlalchemy.orm import Session

from fastapi import APIRouter, status, HTTPException
from fastapi import Depends
from fastapi import Security, Depends, FastAPI, HTTPException, status, APIRouter, Response, Query, Request

from sqlmodel import select, update, delete

from pydantic import UUID4
from typing import List
import logging

from deps import db, check_api_key, get_auth_user
import models

router = APIRouter()


USR_SDT_FMT = "%d.%m.%y %H:%M:%S"


#
# Meta "tables"
#
@router.get("/tables", dependencies=[Depends(check_api_key)])
def get_tables(response: Response, offset: int = 0, limit: int = Query(default=100, le=100), session = Depends(db.get_session)):
    tables = []
    try:
        metadata = db.reflect()
        if metadata:
            tables = []
            #for tname in metadata.sorted_tables:
            for tname in metadata.tables:
                item = {"id":tname, "key":tname, "uuid":tname, "name":tname}
                if tname == "auth_group":
                    item["readonly"] = True
                else:
                    item["readonly"] = False
                tables.append(item)
        else:
            tables = [
                {"id":"orgs_id", "name":"orgs"},
                {"id":"user_id", "name":"user"},
                {"id":"auth_id", "name":"auth"},
            ]
        logging.info("tables=%s" % tables)
        # This is necessary for react-admin to work
        response.headers["Content-Range"] = f"0-9/{len(tables)}"
    except:
        logging.exception("Ошибка в tables")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return tables


@router.get("/tables/{tname}", dependencies=[Depends(check_api_key)])
def get_table_fields(tname: str, response: Response, offset: int = 0, limit: int = Query(default=100, le=100), session = Depends(db.get_session)):
    fields = []
    try:
        metadata = db.reflect()
        if metadata:
            #for tname in metadata.sorted_tables:
            if tname in metadata.tables:
                for fld in metadata.tables[tname].c:
                    field = {
                        "id": "%s.%s" % (tname,fld.name),
                        "uuid": "%s.%s" % (tname,fld.name),
                        "name": fld.name,
                        "type": str(fld.type),
                        #"length": fld.type.length,
                        #"fk": str([str(x) for x in fld.foreign_keys]),
                        "fk": str(list(fld.foreign_keys)[0]).split("'")[1].split(".")[0] if fld.foreign_keys else "",
                        "primary_key": fld.primary_key,
                        "unique": fld.unique,
                        "nullable": fld.nullable,
                    }
                    fields.append(field)

        logging.info("fields=%s" % fields)
        # This is necessary for react-admin to work
        response.headers["Content-Range"] = f"0-9/{len(fields)}"
    except:
        logging.exception("Ошибка в table_fields")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return {"id":tname, "fields":fields}


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


#
# Generic CRUD operations
#
def get_model_by_tname(tname: str):
    table_class = None
    logging.info("tname=%s" % tname)
    for attr in dir(models):
        #logging.info("attr=%s" % attr)
        if attr.lower()+"s" == tname:
            table_class = getattr(models, attr)
            base_class  = getattr(models, attr+"Base")
            break

    if table_class:
        return table_class, base_class
    else:
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/{tname}", dependencies=[Depends(check_api_key)])
def get_obj_list(tname: str, response: Response, offset: int = 0, limit: int = Query(default=100, le=100), session = Depends(db.get_session)):
    model, base = get_model_by_tname(tname)
    logging.info("get_obj_list")
    recs = []
    try:
        recs = db.get_obj_list(model) # session.exec(select(model)).all()
        # This is necessary for react-admin to work
        response.headers["Content-Range"] = f"0-9/{len(recs)}"
    except:
        logging.exception("Ошибка в get_obj_list")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")

    if not recs:
        raise HTTPException(status_code=404, detail="Not found")

    return recs


@router.get("/{tname}/{uuid}", dependencies=[Depends(check_api_key)])
def get_obj_by_id(tname: str, uuid:UUID4, session = Depends(db.get_session)):
    model, base = get_model_by_tname(tname)
    logging.info("get_obj_by_id: %s" % uuid)
    obj = {}
    try:
        obj = db.get_obj_by_id(model, uuid) # session.get(model, uuid)
        if not obj:
            logging.info("%s with id=%s not found" % (tname, uuid))
            raise HTTPException(status_code=404, detail="%s not found" % tname)
    except:
        logging.exception("Ошибка в get_obj_by_id")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return obj


@router.post("/{tname}", dependencies=[Depends(check_api_key)])
def add_obj(tname: str, obj: dict, session = Depends(db.get_session)):
    model, base = get_model_by_tname(tname)
    logging.info("add_obj: %s" % obj)
    try:
        new_rec = db.add_obj(model, base, obj)
        logging.info("%s created: %s" % (tname, str(new_rec)))
    except:
        logging.exception("Ошибка в add_obj")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return new_rec


@router.delete("/{tname}/{uuid}", dependencies=[Depends(check_api_key)])
def del_obj(tname: str, uuid:UUID4, session = Depends(db.get_session)):
    model, base = get_model_by_tname(tname)
    logging.info("del_obj: %s" % uuid)
    try:
        obj = db.del_obj(model, uuid) # session.get(model, uuid)
        if not obj:
            logging.info("%s not found" % tname)
            raise HTTPException(status_code=404, detail="%s not found" % tname)

        logging.info("%s deleted" % tname)
    except:
        logging.exception("Ошибка в del_obj")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return {"result":"OK"}


@router.put("/{tname}/{uuid}", dependencies=[Depends(check_api_key)])
def upd_obj(tname: str, uuid:UUID4, obj: dict, session = Depends(db.get_session)):
    model, base = get_model_by_tname(tname)
    logging.info("upd_obj: %s" % uuid)
    try:
        upd_obj = db.upd_obj(model, base, uuid, obj)
        if not upd_obj:
            logging.info("%s not found" % tname)
            raise HTTPException(status_code=404, detail="%s not found" % tname)
        logging.info("%s updated" % tname)
    except:
        logging.exception("Ошибка в upd_obj")
        raise HTTPException(status_code=400, detail="BAD_REQUEST")
    return upd_obj

