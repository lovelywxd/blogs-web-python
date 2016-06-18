#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
database: User, Blog, Comment.
consider：these three database. how to store data, and the relationship between these three db.
"""
from orm import Model, StringField, BooleanField, FloatField, TextField
import time
import uuid
import logging
logging.basicConfig(level=logging.INFO)


# 用当前时间与随机生成的uuid合成作为id
def next_id():
    #  uuid4()以随机方式生成uuid,hex属性将uuid转为32位的16进制数
    return "%015d%s000" % (int(time.time() * 1000), uuid.uuid4().hex)


class User(Model):
    logging.info("yyyyyyyyyyyyyyyyyyyyyyyyyyyyy")
    __table__ = "users"
    # 为什么default的值会莫名其妙的为None，不是赋值了吗？
    id = StringField(primarykey=True, default=next_id, ddl="varchar(50)")
    email = StringField(ddl="varchar(50)")
    passwd = StringField(ddl="varchar(50)")
    admin = BooleanField()
    name = StringField(ddl="varchar(50)")
    image = StringField(ddl="varchar(500)")
    # 此处default用于存储创建的时间,在insert的时候被调用
    created_at = FloatField(default=time.time)


class Blog(Model):
    __table__ = "blogs"
    id = StringField(primarykey=True, default=next_id, ddl="varchar(50)")
    user_id = StringField(ddl="varchar(50)")
    user_name = StringField(ddl="varchar(50)")
    user_image = StringField(ddl="varchar(500)")
    name = StringField(ddl="varchar(50)")
    summary = StringField(ddl="varchar(200)")
    content = TextField()
    created_at = FloatField(default=time.time)


class Comment(Model):
    __table__ = "comments"
    id = StringField(primarykey=True, default=next_id, ddl="varchar(50)")
    blog_id = StringField(ddl="varchar(50)")
    user_id = StringField(ddl="varchar(50)")
    user_name = StringField(ddl="varchar(50)")
    user_image = StringField(ddl="varchar(500)")
    content = TextField()
    created_at = FloatField(default=time.time)
