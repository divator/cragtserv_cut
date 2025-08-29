# --------------------------------------
# main - Основной модуль
# --------------------------------------

import os
import signal
import sys
import traceback
import logging
import configparser
import uuid
import json
import aio_pika
from pika import BasicProperties
import queue
import threading
from contextlib import asynccontextmanager
import asyncio

from typing import List, Union
from fastapi import Security, Depends, FastAPI, HTTPException, status, APIRouter, Response, Query, Request
from fastapi import File, UploadFile
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import (
    APIKeyHeader, APIKeyCookie, APIKeyQuery,
    HTTPAuthorizationCredentials, HTTPBearer
)

from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from fastapi_utils.tasks import repeat_every


from sqlmodel import select, update, delete
from pydantic import UUID4
#from starlette.requests import Request

import uvicorn


from deps import db, check_api_key
import dbmgr
import models
import cmds

import route_auth
import route_user
import route_meta

#
# Main app and startup
#
broker = None
task_scanner = cmds.TaskFSScaner("tasks", broker)

@repeat_every(seconds=3)
async def scan_dirs_periodically():
    await task_scanner.run_scan()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    print("lifespan start!")
    #await db.init_db("repo")

    # first run MUST be on startup
    # broker NOT yet initialized here
    asyncio.create_task(scan_dirs_periodically())

    #print("lifespan router.lifespan_context!")
    #async with router.lifespan_context(app):
    #    yield

    yield
    # Shutdown code
    print("lifespan exit!")

app = FastAPI(lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["POST","PUT","DELETE","GET","OPTIONS"],
    expose_headers=["Content-Range"],
    allow_headers=["*"],
    )

@app.middleware("http")
async def log_request_middleware(request: Request, call_next):
    # Intercept and modify the incoming request
    logging.debug("%s %s start %s" % (request.method.upper(), request.url, request.client.host))
    # Process the modified request
    response = await call_next(request)
    logging.debug("%s %s %s end"   % (request.method.upper(), request.url, response.status_code))
    return response

api_router = APIRouter()
api_router.include_router(route_auth.router, prefix="/auth" , tags=["auth"])
api_router.include_router(route_user.router, prefix="/user" , tags=["user"])
api_router.include_router(route_meta.router, prefix="/meta" , tags=["meta"])
app.include_router(api_router)

#@router.get("/send_msg")
#async def hello_http():
#    res = await broker.publish({"text":"Testing sync", "number":12345}, "test.queue.from1c")
#    print("Put msg to test result: ",res)
#    return "Hello, HTTP! RMQ message sended!"
#
#app.include_router(router)

@app.get("/ping")
def pong():
    return {"ping": "pong!"}


@app.get("/shutdown")
def shutdown():
    os.kill(os.getpid(), signal.SIGTERM)
    return Response(status_code=200, content='Server shutting down...')

app.mount("/static", StaticFiles(directory="static", html = True), name="static")
app.mount("/"      , StaticFiles(directory="static", html = True), name="static")


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    print("Exception(StarletteHTTPException)")
    logging.error("Exception(StarletteHTTPException) in %s %s: %s" % (request.method, request.url, exc))
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print("Exception(RequestValidationError)")
    logging.error("Exception(RequestValidationError) in %s %s: %s" % (request.method, request.url, exc))
    try:
        err = "".join(traceback.format_tb(exc.__traceback__)) + str(type(exc)) + ":" + str(exc)
        logging.error("Exception(Exception): %s" % err)
    except:
        logging.exception("Exception(RequestValidationError) in %s %s:" % (request.method, request.url))

    return await request_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def all_exception_handler(request, exc):
    print("Exception(Exception)")
    logging.error("Exception(Exception) in %s %s: %s" % (request.method, request.url, exc))
    try:
        #for name in dir(exc):
        #    print(name)
        #print("Exception(Exception): %s" % exc.__traceback__)
        err = "".join(traceback.format_tb(exc.__traceback__)) + str(type(exc)) + ":" + str(exc)
        logging.error("Exception(Exception): %s" % err)
    except:
        logging.exception("Exception(Exception) in %s %s:" % (request.method, request.url))
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


#
# Resources
#
@app.get("/")
def gui():
    return RedirectResponse("/static/index.html")  


@app.get("/firebase-messaging-sw.js", include_in_schema=False)
async def firebase():
    logging.info("/firebase-messaging-sw.js")
    file_name = "firebase-messaging-sw.js"
    file_path = os.path.join(app.root_path, "static", file_name)
    return FileResponse(path=file_path, headers={"Content-Disposition": "attachment; filename=" + file_name})


#@app.get("/docs", include_in_schema=False)
#def custom_swagger_ui_html(req: Request):
#    root_path = req.scope.get("root_path", "").rstrip("/")
#    openapi_url = root_path + app.openapi_url
#    return get_swagger_ui_html(
#        openapi_url=openapi_url,
#        title="API",
#    )

#@app.get("/protected", dependencies=[Depends(check_api_key)])
@app.get("/protected")
def add_post(api_key: str) -> dict:
    if api_key in api_keys:
        return {"data": "You used a valid API key."}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Forbidden"
        )


@app.post("/protected2", dependencies=[Depends(check_api_key)])
def add_post(api_key: str) -> dict:
    return {
        "data": "You used a valid API key."
    }

#
# Основной код запуска микросервиса
#
if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "md5":
            import hashlib
            md5hash = hashlib.md5(sys.argv[2].encode('utf-8')).hexdigest()
            print(md5hash)

        elif sys.argv[1] == "dosql":
            pass
        exit(1)

    ininame = "cragtsrv.ini"
    if os.path.exists(ininame):
        try:
            config_parser = configparser.RawConfigParser()
            config_parser.read(ininame, encoding="utf-8-sig")
            logging.config.fileConfig(config_parser)
        except UnicodeDecodeError:
            config_parser = configparser.RawConfigParser()
            config_parser.read(ininame, encoding="cp1251")
            logging.config.fileConfig(config_parser)

    logging.addLevelName(logging.CRITICAL, 'CRIT')
    logging.addLevelName(logging.ERROR   , 'ERRO')
    logging.addLevelName(logging.WARNING , 'WARN')
    logging.addLevelName(logging.DEBUG   , 'DEBG')
    logging.addLevelName(logging.NOTSET  , 'NSET')
    logging.info("Config loaded.")

    db.init_db()
    try:
        print("Run on 0.0.0.0:8888...")
        # HTTP
        uvicorn.run(app, host="0.0.0.0", port=8888, reload=False, log_level="debug", #debug=True,
                    workers=1, limit_concurrency=10, limit_max_requests=1000)

        # HTTPS
        #uvicorn.run(app, host="0.0.0.0", port=8888, reload=False, log_level="debug", #debug=True,
        #            workers=1, limit_concurrency=20, limit_max_requests=1000,
        #            ssl_keyfile="./privkey1.pem",
        #            ssl_certfile="./fullchain1.pem")
    except:
        logging.exception("Uvicorn error:")

