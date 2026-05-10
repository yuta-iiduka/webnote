# 外部ライブラリのインポート
from flask import (
    Flask,Blueprint,
    redirect,render_template,jsonify,url_for,make_response,request,flash,send_file
)
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO, emit, send,join_room,leave_room,close_room,rooms,disconnect,ConnectionRefusedError
from flask_migrate import Migrate
from flask_login import (
    LoginManager, UserMixin, current_user,
    login_required, login_user, logout_user
)

# 標準モジュールのインポート
import importlib,mimetypes,asyncio

# モデルのインポート
from db.db import *
# スケジュールのインポート
from job.task import * 
from common.logger import *
# ファイルロード
from common.file import *
from common.flask_wrapper import SingletonFlask
# from src.blog import bp as blog

const = JsonData("etc/config/settings.json").data

sf = SingletonFlask(__name__)
socketio = sf.socketio
migrate = sf.migrate
csrf = sf.csrf
app = sf.app
udp_server = sf.udp_server
udp_client = sf.udp_client

app.config["SECRET_KEY"] = "xxxxxxxx"
app.config['JSON_AS_ASCII'] = False
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sqlite.db'
# app.config["SQLALCHEMY_BINDS"] = {
#     "sticky": constant["SQLALCHEMY_DATABASE_URI"],
#     "card": constant["SQLALCHEMY_DATABASE_URI_CARD"]
# }

login_manager = sf.login_manager
login_manager.login_view = "login"
login_manager.login_message = ""
@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id=user_id).first()

@app.context_processor
def inject_const():
    return const

def create_app():
    global socketio, app, aps

    # 各機能を初期化
    db.init_app(app)
    # login_manager.init_app(app)
    dd = DirData("src")
    for m in dd.files.keys():
        if "bp.py" in m:
            module = importlib.import_module(m.replace("/",".").replace(".py",""))
            if hasattr(module,"bp"):
                app.register_blueprint(module.bp)

    # URL Route
    for rule in app.url_map.iter_rules():
        print(rule,rule.endpoint)

    # Socket Route
    print(socketio.server.handlers)
    print(socketio)

    aps.init_app(app)
    aps.start()

    return app


@udp_server.callback
async def test(data,addr):
    print("test recieve from",addr,data)

@udp_client.callback
async def test(data,addr):
    print("test recieve from",addr,data)

@udp_client.receive
async def _res(data,addr):
    print("[CLIENT] recieve from",addr,data)

@udp_server.receive
async def _res(data,addr):
    print("[SERVER] recieve from",addr,data)

async def main():
    
    udp_server.run()
    udp_client.run()
    print(udp_server,udp_server.transport,udp_server.event_loop)
    print(udp_client,udp_client.transport,udp_client.event_loop)
    udp_server.coroutine(udp_server.sendto({"type":"test","message":"OK"},("::1",9998)))

    udp_server.run_worker()
    udp_client.run_worker()
    # sf.run(create_app(), const["app_host"], const["app_port"])
    socketio.run(create_app(), const["app_host"], const["app_port"])

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    """
    # windows
    $env:FLASK_APP = "server:create_app()"
    py -m flask db init
    py -m flask db migrate
    py -m flask db upgrade
    
    py server.py

    
    # linux
    gunicorn -c src/gunicorn.conf.py server:create_app()

    """
    print(const)
    asyncio.run(main())
    