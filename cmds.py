# --------------------------------------
# cmds - Модуль обработки запросов RMQ 
#        к серверу
# --------------------------------------

import logging
import json
import uuid
import time
import datetime
import os
import base64
import requests

import aio_pika
from pika import BasicProperties

import models
from deps import db, check_api_key


TMP_TIME_FMT = "%Y%m%d_%H%M%S_%f"
TMP_DATE_FMT = "%Y%m%d"
JSON_TIME_FMT = "%Y-%m-%dT%H:%M:%S.%fZ" #2017-11-26T09:10:15.123Z

# Login Types
LT_UNKNOWN = 0
LT_LOGIN   = 1
LT_LOGOUT  = 2
LT_OTHER   = 3 # registration


def cmd_login(message, body):
    reply = {"error":""}
    agt_id = ""
    lic_id = ""
    try:
        data   = json.loads(body.decode("utf-8"))
        cmd    = data["cmd"   ]
        hname  = data["hname" ]
        agt_id = data["agt_id"]
        lic_id = data["lic_id"]
        chlt   = data["chlt"  ]
        clnt   = data["clnt"  ]
    except:
        reply = {"error":"Нарушение формата данных"}
        logging.exception("Ошибка в разборе команды login (data=%s)" % body)

    if not reply["error"]:
        try:
            if agt_id and lic_id:
                lic = db.get_obj_by_id(models.Lic  , lic_id)
                if lic:
                    agent = db.get_obj_by_id(models.Agent, agt_id)
                    if agent:
                        logging.info("LOGIN Agent found: lic_id=%s, agt_id=%s" % (lic_id, agt_id))
                        reply["data"] = {"agt_id":agt_id}
                    else:
                        reply = {"error":"Неверный код агента"}
                else:
                    reply = {"error":"Лицензия недействительна"}
            else:
                reply = {"error":"Нет лицензии или кода агента"}

            if reply["error"]:
                logging.info("Ошибочная авторизация lic_id='%s' agt_id='%s': %s" % (lic_id, agt_id, reply["error"]))
                logging.error(reply["error"])
            else:
                logging.info("Успешная авторизация lic_id='%s' agt_id='%s'" % (lic_id, agt_id))
        except:
            reply = {"error":"Нарушение обработки данных"}
            logging.exception("Ошибка в обработке команды login (data=%s)" % body)

        # Логируем логин агента в БД
        login_rec = {
            "agent"   : agt_id,
            "ltype"   : LT_LOGIN,
            "req"     : body.decode("utf-8"),
            "rsp"     : str(reply),
            "success" : not reply["error"],
        }
        login = db.add_obj(models.Login, models.LoginBase, login_rec)

    reply_msg = make_reply_msg(message, reply)
    return reply_msg


def cmd_logout(message, body):
    reply = {"error":""}
    agt_id = ""
    lic_id = ""
    try:
        data   = json.loads(body.decode("utf-8"))
        cmd    = data["cmd"   ]
        hname  = data["hname" ]
        agt_id = data["agt_id"]
        lic_id = data["lic_id"]
        chlt   = data["chlt"  ]
        clnt   = data["clnt"  ]
    except:
        reply = {"error":"Нарушение формата данных"}
        logging.exception("Ошибка в разборе команды logout (data=%s)" % body)

    if not reply["error"]:
        try:
            if agt_id and lic_id:
                lic = db.get_obj_by_id(models.Lic  , lic_id)
                if lic:
                    agent = db.get_obj_by_id(models.Agent, agt_id)
                    if agent:
                        logging.info("LOGOUT Agent found: lic_id=%s, agt_id=%s" % (lic_id, agt_id))
                        reply["data"] = {"agt_id":agt_id}
                    else:
                        reply = {"error":"Неверный код агента"}
                else:
                    reply = {"error":"Лицензия недействительна"}
            else:
                reply = {"error":"Нет лицензии или кода агента"}

            if reply["error"]:
                logging.info("Ошибочная авторизация lic_id='%s' agt_id='%s': %s" % (lic_id, agt_id, reply["error"]))
                logging.error(reply["error"])
            else:
                logging.info("Успешная авторизация lic_id='%s' agt_id='%s'" % (lic_id, agt_id))
        except:
            reply = {"error":"Нарушение обработки данных"}
            logging.exception("Ошибка в обработке команды logout (data=%s)" % body)

        # Логируем логин агента в БД
        login_rec = {
            "agent"   : agt_id,
            "ltype"   : LT_LOGOUT,
            "req"     : body.decode("utf-8"),
            "rsp"     : str(reply),
            "success" : not reply["error"],
        }
        login = db.add_obj(models.Login, models.LoginBase, login_rec)

    reply_msg = make_reply_msg(message, reply)
    return reply_msg


def cmd_reg(message, body):
    reply = {"error":""}
    agt_id = ""
    lic_id = ""
    try:
        data   = json.loads(body.decode("utf-8"))
        cmd    = data["cmd"   ]
        hname  = data["hname" ]
        agt_id = data["agt_id"]
        lic_id = data["lic_id"]
        chlt   = data["chlt"  ]
        clnt   = data["clnt"  ]
    except:
        reply = {"error":"Нарушение формата данных"}
        logging.exception("Ошибка в разборе команды reg (data=%s)" % body)

    if not reply["error"]:
        try:
            reply = db.bl_reg_agent(lic_id, hname)

            if reply["error"]:
                logging.info("Ошибочная регистрация lic_id='%s' agt_id='%s': %s" % (lic_id, agt_id, reply["error"]))
                logging.error(reply["error"])
            else:
                logging.info("Регистрация: %s" % reply)
                agt_id    = str(reply["data"]["uuid"])
                agt_qname = str(reply["data"]["agt_qname"])
                logging.info("Успешная регистрация lic_id='%s' agt_id='%s'" % (lic_id, agt_id))
                reply["data"] = {"agt_id":agt_id, "agt_qname":agt_qname}
        except:
            reply = {"error":"Нарушение обработки данных"}
            logging.exception("Ошибка в обработке команды reg (data=%s)" % body)

        # Логируем логин агента в БД
        success = not reply["error"]
        login_rec = {
            "agent"   : agt_id,
            "ltype"   : LT_LOGIN if success else LT_OTHER,
            "req"     : body.decode("utf-8"),
            "rsp"     : str(reply),
            "success" : success,
        }
        login = db.add_obj(models.Login, models.LoginBase, login_rec)

    reply_msg = make_reply_msg(message, reply)
    return reply_msg


def process_err_msg(message):
    reply = {"error":"Неизвестная команда"}
    reply_msg = make_reply_msg(message, reply)
    return reply_msg


def make_reply_msg(message, reply):
    body = json.dumps(reply).encode("utf-8")

    reply_msg = aio_pika.message.Message(body)
    reply_msg.app_id         = 'cragent'
    reply_msg.type           = 'cmdresult'
    reply_msg.content_type   = 'application/cragent-cmd-v3'
    reply_msg.correlation_id = message.message_id
    reply_msg.message_id     = str(uuid.uuid4())

    logging.info("reply_msg: %s" % str(reply_msg))
    return reply_msg

#
#  File system interface block
#
def read_file(fname):
    f = open(fname, "rb")
    data = f.read()
    f.close()
    return data


def write_file(fname, data):
    f = open(fname, "wb")
    f.write(data)
    f.close()


def save_json(fname, data):
    s = json.dumps(data, ensure_ascii=False, indent=4, sort_keys=True)
    f = open(fname,"wt",encoding="utf-8")
    f.write(s)
    f.close()


def load_json(fname):
    f = open(fname,"rt",encoding="utf-8")
    data = json.load(f)
    f.close()
    return data


def check_and_make_dir(path):
    if not os.path.exists(path):
        logging.info("Каталог '%s' не существует. Создание." % path)
        try:
            os.makedirs(path)
        except WindowsError as e:
            if e.winerror == 183:  # ERROR_ALREADY_EXISTS
                pass
            else:
                raise

def get_arc_fname(name, out=True, src_fname="", now=None):
    root_dir = "tasks/"

    if not now:
        now = datetime.datetime.now()
    now_date = now.strftime(TMP_DATE_FMT)
    now_str = now.strftime(TMP_TIME_FMT)
    if out:
        arco_dir = os.path.join(root_dir, "arc", now_date, name, "out")
    else:
        arco_dir = os.path.join(root_dir, "arc", now_date, name, "in")
    check_and_make_dir(arco_dir)

    arc_name = "%s_%s" % (now_str, src_fname)
    arc_fullname = os.path.join(arco_dir, arc_name)
    return arc_fullname


def get_agt_fname(name, out=True, src_fname="", now=None):
    root_dir = "tasks/"

    if not now:
        now = datetime.datetime.now()
    now_str = now.strftime(TMP_TIME_FMT)
    if out:
        agt_dir = os.path.join(root_dir, "agents", name, "out")
    else:
        agt_dir = os.path.join(root_dir, "agents", name, "in")
    check_and_make_dir(agt_dir)

    agt_name = "%s_%s" % (now_str, src_fname)
    agt_fullname = os.path.join(agt_dir, agt_name)
    return agt_fullname


def get_fail_fname(name, out=True, src_fname="", now=None):
    root_dir = "tasks/"

    if not now:
        now = datetime.datetime.now()
    now_str = now.strftime(TMP_TIME_FMT)

    fail_dir = os.path.join(root_dir, "fails")
    check_and_make_dir(fail_dir)

    direction = "out" if out else "inc"
    fail_name = "%s_%s_%s_%s" % (now_str, direction, name, src_fname)
    fail_fullname = os.path.join(fail_dir, fail_name)
    return fail_fullname


def cleanup_file_name(Dirty):
    # failed on NON-ACSII
    # trans = string.maketrans(r"\>:</","_____")
    # clean = string.translate( Dirty, trans)

    clean = ""
    for c in Dirty:
        if (c in r'\>:|</?*"') or (ord(c) < 32):
            clean += "_"
        else:
            clean += c
    return clean


def get_unique_name(fname):
    uniqueFileName = fname
    copy = 1
    while os.path.exists(uniqueFileName):
        (root, ext) = os.path.splitext(fname)
        uniqueFileName = root + "_" + str(copy) + ext
        copy += 1
    return uniqueFileName


def save_file_data(fname, fdata):
    try:
        (dirname, filename) = os.path.split(fname)
        file_name = fdata["name"]
        file_size = fdata["size"]
        file_data = fdata["data"]

        file_data_bin = base64.b64decode(file_data)

        # make unique file name for save
        only_fname = os.path.basename(file_name)
        clean_fname = cleanup_file_name(only_fname)
        create_fname = os.path.join(dirname, clean_fname)
        save_fname = get_unique_name(create_fname)

        write_file(save_fname, file_data_bin)

        if len(file_data_bin) == file_size:
            logging.info("Файл из сообщения '%s':'%s' (%d байт) сохранён в '%s'" % (fname, file_name, file_size, save_fname))
        else:
            logging.error("Ошибка в размере файла %d (факт), должно быть %d. Файл из сообщения '%s':'%s' сохранён в '%s'" % (len(file_data_bin), file_size, fname, file_name, save_fname))
    except:
        logging.exception("Ошибка извлечения файла из тела сообщения '%s'" % fname)


def save_task_reply(name, reply_msg, reply_body):
    root_dir = "tasks/"

    now = datetime.datetime.now()
    now_str = now.strftime(TMP_TIME_FMT)

    fname = reply_msg.message_id
    processed = False
    
    try:
        reply_data = json.loads(reply_body)

        if name:
            agt_fullname = get_agt_fname(name, out=False, src_fname=fname, now=now)
            write_file(agt_fullname, reply_body)
            logging.info("Файл '%s' помещён в приём как '%s'" % (fname, agt_fullname))

            if (
                ("data" in reply_data) and
                ("size" in reply_data) and
                ("name" in reply_data)
               ):
               save_file_data(agt_fullname, reply_data)

            arc_fullname = get_arc_fname(name, out=False, src_fname=fname, now=now)
            write_file(arc_fullname, reply_body)
            logging.info("Файл '%s' помещён в архив как '%s'" % (fname, arc_fullname))
            processed = True
        else:
            logging.exception("Ошибка: не удалось определить имя агента (MSG=%s)" % reply_msg)
    except:
        logging.exception("Ошибка при обработке ответа на задачу (MSG=%s)" % reply_msg)

    if not processed:
        fail_fname = get_fail_fname(name, out=False, src_fname="", now=now)
        write_file(fail_fname+".msg" , str(reply_msg).encode("utf-8"))
        write_file(fail_fname+".body", reply_body)


class TaskFSScaner():
    def __init__(self, task_dir, broker):
        self.task_dir = task_dir
        self.broker   = broker
        self.first_run = True
        self.last_crmon_send = None

        cfg_fname = os.path.join(self.task_dir, "cc.json")
        self.config = load_json(cfg_fname)
        for name, agent_cfg in self.config["agents"].items():
            self.init_agent(name, agent_cfg)


    def init_agent(self, name, cfg):
        check_and_make_dir(os.path.join(self.task_dir, "fails"))
        check_and_make_dir(os.path.join(self.task_dir, "agents", name))
        check_and_make_dir(os.path.join(self.task_dir, "agents", name, "in"))
        check_and_make_dir(os.path.join(self.task_dir, "agents", name, "out"))
        check_and_make_dir(os.path.join(self.task_dir, "arc"))


    def get_agent_name_by_id(self, agent_id):
        agt_name = ""
        for name, agent_cfg in self.config["agents"].items():
            if agent_cfg["id"] == agent_id:
                agt_name = name
                break
        return agt_name

        
    async def save_reply(self, reply_msg, reply_body):
        # reply_to == agent_id
        name = self.get_agent_name_by_id(reply_msg.reply_to)
        save_task_reply(name, reply_msg, reply_body)


    async def send_file(self, name, cfg, fullname):
        # 1. Put file to archive
        dirname, fname = os.path.split(fullname)

        now = datetime.datetime.now()
        arc_fullname = get_arc_fname(name, out=True, src_fname=fname, now=now)

        os.rename(fullname, arc_fullname)
        logging.info("Файл '%s' помещён в архив как '%s'" % (fullname, arc_fullname))

        # 2. Send message to queue
        try:
            msg_data = {}
            try:
                msg_data = load_json(arc_fullname)
            except:
                logging.exception("Файл '%s' не в формате JSON" % arc_fullname)

            if msg_data:
                exchange      = msg_data.get("connection.exchange"   , "")
                routing_key   = msg_data.get("connection.routing_key", cfg["cmd_queue"])

                body          = msg_data.get("body"                       )
                body_decode   = msg_data.get("body.decode", False         )
                body_fname    = msg_data.get("body.fname"                 )
                                                                                        
                if not body and body_fname:
                    body = read_file(body_fname)
                    del msg_data["body.fname"]
                    msg_data["body"] = base64.b64encode(body).decode("ascii")
                else:
                    if body_decode:
                        body = base64.b64decode(body)
                    else:
                        body = body.encode("utf-8")

                if not msg_data.get("properties.message-id"):
                    msg_data["properties.message-id"] = str(uuid.uuid4())
                
                save_json(arc_fullname+".msg", msg_data)

                # make command for agent message
                #body = json.dumps(reply).encode("utf-8")

                reply_msg = aio_pika.message.Message(body)
                reply_msg.content_type     = msg_data.get("properties.content-type"    )
                reply_msg.content_encoding = msg_data.get("properties.content-encoding")
                reply_msg.headers          = msg_data.get("properties.headers"         )
                #reply_msg.delivery_mode    = msg_data.get("properties.delivery-mode"   )
                reply_msg.priority         = msg_data.get("properties.priority"        )
                reply_msg.correlation_id   = msg_data.get("properties.correlation-id"  )
                reply_msg.reply_to         = msg_data.get("properties.reply-to"        )
                #reply_msg.expiration       = msg_data.get("properties.expiration"      )
                reply_msg.message_id       = msg_data.get("properties.message-id"      )
                #reply_msg.timestamp        = msg_data.get("properties.timestamp"       )
                reply_msg.type             = msg_data.get("properties.type"            )
                reply_msg.user_id          = msg_data.get("properties.user-id"         )
                reply_msg.app_id           = msg_data.get("properties.app-id"          )

                logging.info("Отправляем сообщение %s ..." % reply_msg)
                res = await self.broker.publish(reply_msg, routing_key)
                logging.info("Отправлено сообщение (res=%s)" % res)

            else:
                fail_fullname = get_fail_fname(name, out=True, src_fname=fname, now=now)
                data = read_file(arc_fullname)
                write_file(fail_fullname, data)
                logging.info("Ошибочный файл сохранён в '%s'" % fail_fullname)
        except:
            logging.exception("Ошибка при отправке сообщения '%s'" % fullname)
        return None


    async def check_send_dirs(self, name, cfg):
        send_dir = os.path.join(self.task_dir, "agents", name, "out")
        for fname in os.listdir(send_dir):
            fullname = os.path.join(send_dir, fname)
            if os.path.isfile(fullname):
                logging.info("Обнаружен файл '%s' ..." % fullname)
                await self.send_file(name, cfg, fullname)


    def crmon_send(self):
        # вырезано :^)
        pass


    async def run_scan(self):
        """ Периодически сканирует каталоги и отправляет 
            найденные в них файлы описания сообщений в очереди
        """
        if self.first_run:
            # Первый запуск идёт до старта propan broker
            logging.info("Процесс сканирования каталогов задач запущен.")
            self.first_run = False
        else:
            try:
                # Сканируем каталоги и отправляем файлы
                for name, agent_cfg in self.config["agents"].items():
                    await self.check_send_dirs(name, agent_cfg)

                # Отправляем данные о состоянии агентов в Мониторинг каждые 60 сек.
                now = datetime.datetime.now()
                if (self.last_crmon_send is None) or ((now - self.last_crmon_send).total_seconds() > 60):
                    self.crmon_send()
                    self.last_crmon_send = datetime.datetime.now()
            except:
                logging.exception("Ошибка в процессе сканирования каталогов задач")
