import threading, asyncio
from common.communication import *
from flask import Flask
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from db.db import db

class SingletonFlask:

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self,name):
        if SingletonFlask._initialized:
            return
        else:
            self.app =Flask(name)
            self.login_manager = LoginManager(self.app)
            self.socketio = SocketIO(self.app, cors_allowed_origins="*")
            self.migrate = Migrate(self.app, db)
            self.csrf = CSRFProtect(self.app)
            self.udp_server = UDPServer(host="::1",port=9999)
            self.udp_client = UDPClient(host="::1",port=9999,local_port=9998)

            SingletonFlask._initialized = True
        
    def run(self,*args):
        t = threading.Thread(target=self.socketio.run, args=args, daemon=True)
        t.start()
        return t