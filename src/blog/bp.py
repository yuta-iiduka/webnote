
# from flask import (
#     Blueprint,render_template,redirect,jsonify,
#     url_for,flash
# )
# from flask_login import login_required
# from db.db import db
# from common.logger import logger, log
from server import *

NAME = "blog"
URL_PREFIX = "/{}".format(NAME)
bp = Blueprint(NAME, __name__, url_prefix=URL_PREFIX)

@bp.route("/",methods=["GET"])
@login_required
def index():
    return render_template("blog/index.html")

@bp.route("/create",methods=["GET"])
@login_required
def create():
    return render_template("blog/create.html")