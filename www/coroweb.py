"""
定义@get，@post。 然后写URL handler的时候，可以使用相应方法包装。
具体处理URL流程
"""
import asyncio
import functools
# python中的自省模块，类似完成Java一样的反射功能。
import inspect
import logging
import os
from aiohttp import web
from urllib import parse
from apis import APIError


# --------------get和post装饰器，用于增加__method__和__route__特殊属性，分别标记GET,POST方法和path
def get(path):
    def decorator(func):
        """define decorator @get('/path')"""
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator


def post(path):
    """define decorator @post('/path')"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator


# keyword,且未指定关键值
def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)


# keyword
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


# has_keyword ?命名关键字参数：参数类型：KEYWORD_ONLY
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True


# has var_kw ?VAR_KEYWORD
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True


# has request? 属于*kw或者**kw或者*或者*args之后的参数
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == "request":
            found = True
            continue
        # understand ?? 必须是最后一个参数？
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError("request parameter must be the last named parameter in function: %s%s" % (fn.__name__, str(sig)))
    return found


# 从request中获得需要的参数，具体需要获得哪些参数，要看相应的request process需要哪些参数。
# 主要目的是为了简化URL工作，因为所有的URL处理，都需要分析request中的参数，然后进行处理。
# 问题：
# 第一：如何从URL处理函数中，分析其需要接收的参数？ 参数类型：
# 第二：从request提取从URL处理函数中分析需要的参数，然后传参数给URL处理函数，调用。
class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        #
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)

    # __call__方法的代码逻辑:
    # 1.定义kw对象，用于保存参数
    # 2.判断request对象是否存在参数，如果存在则根据是POST还是GET方法将参数内容保存到kw
    # 3.如果kw为空(说明request没有传递参数)，则将match_info列表里面的资源映射表赋值给kw；
    # 如果不为空则把命名关键字参数的内容给kw
    # 4.完善_has_request_arg和_required_kw_args属性
    @asyncio.coroutine
    def __call__(self, request):
        kw = None
        # 首先从request获取所有能够获得的参数，然后再去决定如何传参。
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == "POST":
                if not request.content_type:
                    logging.info("11111111111111111111111111111")
                    return web.HTTPBadRequest('Missing Content-Type')
                ct = request.content_type.lower()
                if ct.startswith("application/json"):
                    params = yield from request.json()
                    logging.info(params)
                    if not isinstance(params, dict):
                        logging.info("22222222222222222222222222222")
                        return web.HTTPBadRequest("JSON body must be object")
                    # 刚才，搞忘了这一句出错了
                    kw = params
                elif ct.startswith("application/x-www-form-urlencoded") or ct.startswith("multipart/form-data"):
                    params = yield from request.post()
                    kw = dict(**params)
                else:
                    logging.info("3333333333333333333333333333333333")
                    return web.HTTPBadRequest("Unsupported Content-type: %s" % request.content_type)
            if request.method == "GET":
                # 查询字符串
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        # 未从request中获取到参数
        if kw is None:
            # request.match_info是一个dict
            kw = dict(**request.match_info)
        else:
            # url处理函数没有VAR_KEYWORD  只有KEYWORD_ONLY
            # 从request_content中删除URL处理函数中所有不需要的参数
            if not self._has_var_kw_arg and self._named_kw_args:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
                for k, v in request.match_info.items():
                    if k in kw:
                        logging.warnning('Duplicate arg name in named arg and kw args: %s' % k)
                    kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # 之前默认为空的关键字，必须传入参数。检查kw中是否已经获得这些参数
        if self._required_kw_args:
            for name in self._required_kw_args:
                if name not in kw:
                    logging.info("4444444444444444444444444444444444444")
                    # return web.HTTPBadRequest()
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info("call with args: %s" % str(kw))
        logging.info(str(self._func))
        try:
            r = yield from self._func(**kw)
            return r
        # understand ?? how to use ? Inside the handler.
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


# 添加CSS等静态文件所在路径
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))


def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutine(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ','.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))


# 扫描模块 module_name，获取里面的URL_handler，然后注册
def add_routes(app, module_name):
    n = module_name.rfind('.')
    print(n)
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        # mod = __import__(module_name[:n], globals(), locals())
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)


