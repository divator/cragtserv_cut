# --------------------------------------
# security - Утилиты безопасности
# --------------------------------------
import hashlib
import logging
import string
import random

def gen_random_pwd(length):
    password = ''
    #specials = r'~!@#$%^&*_+-=`,./<>?:"\'\\|(){}[]'
    specials = r'~!@#$%^&*()_+-=?<>,.:;{}[]|'
    for i in range(0, length):
        password += random.choice(string.ascii_lowercase)
        password += random.choice(string.ascii_uppercase)
        password += random.choice(string.digits)
        password += random.choice(specials)

    pwd_chars = list(password[0:length])
    random.shuffle(pwd_chars)
    pwd_str = ''.join(pwd_chars)
    return pwd_str


def make_pwd_hash(pwd):
    pwd_hash = hashlib.md5(pwd.encode('utf-8')).hexdigest()
    return pwd_hash


