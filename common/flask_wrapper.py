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
            SingletonFlask._initialized = True
        