
# Redisサーバ構築
```
# Windows
# Donwload: https://www.memurai.com/get-memurai?version=windows-valkey
# 管理者権限でインストール(Windows版)
Get-Service *memurai*
Start-Service Memurai
Stop-Service Memurai
Restart-Service Memurai

# Linux
# https://rhel.pkgs.org/8/raven-modular-x86_64/redis-7.0.5-1.el8.x86_64.rpm.html

pip install redis,celery
```


``` python

socketio = SocketIO(
    app,
    message_queue="redis://127.0.0.1:6379/0"
)
```
``` python
# celery_app.py

from celery import Celery

celery = Celery(
    "tasks",
    broker="redis://localhost:6379/1",
    backend="redis://localhost:6379/2"
)

@celery.task
def heavy_task(user_id):
    pass

```