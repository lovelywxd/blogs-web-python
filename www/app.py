#! /usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import json
import time
import orm
import os
from datetime import datetime
from handlers import cookie2user, COOKIE_NAME
from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from coroweb import add_routes, add_static
import logging
logging.basicConfig(level=logging.INFO)


# 模板引擎，即往模板里面填东西(相当于匹配). Understand ?
def init_jinja2(app, **kw):
    logging.info('init jinja2....')
    options = dict(
        # 自动转义xml/html的特殊字符
        autoescape=kw.get('autoescape', True),
        block_start_string=kw.get('block_start_string', '{%'),
        block_end_string=kw.get('block_end_string', '%}'),
        variable_start_string=kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
        auto_reload=kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        logging.info('set jinja2 template path: %s' % path)
    # 
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filter', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env


# ------------------------------------------拦截器middlewares设置-------------------------
# 日志处理. 这里的handler是auth_factory.auth
@asyncio.coroutine
def logger_factory(app, handler):
    @asyncio.coroutine
    def logger(request):
        logging.info("Request: %s %s " % (request.method, request.path))
        logging.info(request.text())
        return (yield from handler(request))
    return logger


# 解析数据 感觉并没有什么用。因为在RequestHandler里面会做更详细的处理
@asyncio.coroutine
def data_factory(app, handler):
    @asyncio.coroutine
    def parse_data(request):
        if request.method == "POST":
            if request.content_type.startwith("application/json"):
                # request.json方法,读取消息主题,并以utf-8解码
                request.__data__ = yield from request.json()
                logging.info("request json: %s" % str(request.__data__))
            elif request.content_type.startwith("application/x-www-form-urlencoded"):
                request.__data__ = yield from request.host()
                logging.info("request form: %s" % str(request.__data__))
        return (yield from handler(request))
    return parse_data


@asyncio.coroutine
def auth_factory(app, handler):
    @asyncio.coroutine
    def auth(request):
        logging.info("check user: %s %s" % (request.method, request.path))
        request.__user__ = None
        logging.info(request.cookies)
        cookie_str = request.cookies.get(COOKIE_NAME)

        if cookie_str:
            user = yield from cookie2user(cookie_str)
            if user:
                logging.info("set current user: %s" % user.email)
                request.__user__ = user
        logging.info(request.__user__)
        # logging.info(request.__user__.admin)
        # 请求的路径是管理页面,但用户非管理员,将会重定向到登录页
        # if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
        if request.path.startswith('/manage/') and (request.__user__ is None):
            return web.HTTPFound('/signin')
        return (yield from handler(request))
    return auth


# 最后构造response的方法。 URL-handler返回处理结果给response
# response_factory拿到经过处理后的对象，经过一系列类型判断，构造出正确web.Response对象
@asyncio.coroutine
def response_factory(app, handler):
    @asyncio.coroutine
    def response(request):
        logging.info("Response Handler...")
        logging.info(str(handler))
        # the handle result
        r = yield from handler(request)
        logging.info(type(r))
        logging.info('r = %s' % str(r))
        if isinstance(r, web.StreamResponse):
            return r
        # 如果响应结果为字节流，则把字节流塞到response的body里，设置响应类型为流类型，返回
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                # 判断是否需要重定向
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(
                    body=json.dumps(
                        r,
                        ensure_ascii=False,
                        default=lambda o: o.__dict__
                    ).encode('utf-8')
                )
                resp.content_type = "application/json;charset=utf-8"
                return resp
            # 有key值
            else:
                # 如果用jinja2渲染，绑定已验证过的用户
                r['__user__'] = request.__user__
                resp = web.Response(
                    body=app['__templating__'].get_template(template).render(**r).encode('utf-8')
                )
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and 100 <= r < 600:
            return web.Response(status=r)
        if isinstance(r, tuple) and len(r) == 2:
            status, message = r
            if isinstance(status, int) and 100 <= status < 600:
                return web.Response(status=status, text=str(message))
            resp = web.Response(body=str(r).encode('utf-8'))
            resp.content_type = 'text/plain;charset=utf-8'
            return resp
    return response


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


@asyncio.coroutine
def init(loop):
    yield from orm.create_pool(
        loop=loop,
        # host="115.159.219.141",
        host="localhost",
        port=3306,
        user="root",
        password="wxd",
        db="web",
        autocommit=True
    )
    app = web.Application(loop=loop, middlewares=[logger_factory, auth_factory, response_factory])
    init_jinja2(app, filter=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
