from server import *

NAME = "user"
URL_PREFIX = "/{}".format(NAME)
bp = Blueprint(NAME, __name__, url_prefix=URL_PREFIX)

@bp.route("/index",methods=["GET"])
@login_required
def index():
    return render_template("user/index.html")

@bp.route("/",methods=["GET"])
@login_required
def mypage():
    return render_template("user/mypage.html")