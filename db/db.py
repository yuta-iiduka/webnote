from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# 標準ライブラリのインポート
from functools import wraps
import datetime, inspect, sys, json, ast

db = SQLAlchemy()

# デコレータの初期化
def transaction(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            db.session.begin(True)
            result = func(*args, **kwargs)
            db.session.commit()
            return result
            
        except Exception as e:
            db.session.rollback()
            raise e
                
    return wrapper

class BaseColumn(object):
    id         = db.Column(db.Integer, primary_key=True)
    status     = db.Column(db.Integer,  default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    deleted_at = db.Column(db.DateTime, default=None)


class User(db.Model,UserMixin,BaseColumn):
    """ userテーブル
    """
    __tablename__ = "user"
    #__bind_key__ = ""
    name      = db.Column(db.String(64), nullable=True)
    email     = db.Column(db.String(64), nullable=False)
    password_ = db.Column("password", db.String(64), nullable=False ,default="")
    role      = db.Column(db.Integer, default=0)
    group     = db.Column(db.Integer, default=0)
    auth      = db.Column(db.Integer, default=0)

    @property
    def password(self):
        raise AttributeError("読み取り不可")
    
    @password.setter
    def password(self,password):
        self.password_ = generate_password_hash(password)
        
    def verify_password(self, password):
        return check_password_hash(self.password_, password)
        
    def is_duplicate_name(self):
        return User.query.filter_by(name=self.name).first() is not None

    def is_duplicate_email(self):
        return User.query.filter_by(name=self.email).first() is not None

class Test(db.Model,BaseColumn):
    """ testテーブル
    """
    __tablename___ = "test"
    name  = db.Column(db.String(64), nullable=True)
    genre = db.Column(db.Integer, default=0)
    mode  = db.Column(db.Integer, default=0)

class ExamInfo(db.Model,UserMixin,BaseColumn):
    """ test_infoテーブル
    """
    __tablename__ = "test_info"
    test_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, default=0)
    score   = db.Column(db.Integer, default=0)
    is_pass = db.Column(db.Boolean, default=False)
    start   = db.Column(db.DateTime, default=None)
    end     = db.Column(db.DateTime, default=None)
    time    = db.Column(db.Integer, default=30)

class Question(db.Model,BaseColumn):
    """ questionテーブル
    """
    __tablename__ = "question"
    test_id      = db.Column(db.Integer, nullable=False)
    name         = db.Column(db.String(256), nullable=True)
    title        = db.Column(db.String(1024), nullable=True)
    explanation  = db.Column(db.Text, nullable=True)
    mode         = db.Column(db.Integer, default=1)

class AnswerFrame(db.Model,BaseColumn):
    """ answer_frameテーブル
    """
    __tablename__ = "answer_frame"
    quest_id     = db.Column(db.Integer, nullable=False)
    title        = db.Column(db.String(1024), nullable=True)
    explanation  = db.Column(db.Text, nullable=True)
    mode         = db.Column(db.Integer, default=1)
    is_answer    = db.Column(db.Boolean, default=False)
    value        = db.Column(db.Text, default="")

class UserAnswerQuestion(db.Model,BaseColumn):
    """ user_answer_questionテーブル
    """
    __tablename__ = "user_answer_question"
    quest_id     = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, default=0)
    is_pass = db.Column(db.Boolean, default=False)

class UserAnswerFrame(db.Model,BaseColumn):
    """ user_answer_frameテーブル
    """
    __tablename__ = "user_answer_frame"
    user_answer_quest_id     = db.Column(db.Integer, nullable=False)
    value        = db.Column(db.Text, default="")

if __name__ == "__main__":
    pass