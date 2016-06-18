#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL handlers.
"""
import time
import hashlib
import asyncio
import logging
import re
import json
import markdown2
from aiohttp import web
from models import User, Comment, Blog, next_id
from config import configs
from coroweb import get, post
from apis import APIError, APIResourceNotFoundError, APIValueError, APIPermissionError,Page

_COOKIE_KEY = configs.session.secret  # cookie密钥,作为加密cookie的原始字符串的一部分
COOKIE_NAME = 'web_session'  # cookie名,用于设置cookie


def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        return APIPermissionError()


def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p


# 文本转html
def text2html(text):
    """文本转html"""
    # 先用filter函数对输入的文本进行过滤处理: 断行,去首尾空白字符
    # 再用map函数对特殊符号进行转换,在将字符串装入html的<p>标签中
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    # lines是一个字符串列表,将其组装成一个字符串,该字符串即表示html的段落
    return ''.join(lines)


# 通过用户信息计算加密cookie
def user2cookie(user, max_age):
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    # 生成加密的字符串,并与用户id,失效时间共同组成cookie  ???
    l = [user.id, expires, hashlib.sha1(s.encode("utf-8")).hexdigest()]
    return "-".join(l)


# 解密cookie.根据cookie字符串，验证用户登录情况。
# 目的：验证cookie,就是为了验证当前用户是否仍登录着,从而使用户不必重新登录
@asyncio.coroutine
def cookie2user(cookie_str):
    """Parse cookie and load user if cookie is valid"""
    if not cookie_str:
        return None
    try:
        l = cookie_str.split("-")
        if len(l) != 3:
            return None
        uid, expires, sha1s = l
        # 若失效时间小于当前时间,cookie失效
        if int(expires) < time.time():
            return None
        user = yield from User.find(uid)
        if user is None:
            return None
        s = "%s-%s-%s-%s" % (uid, user.passwd, expires, _COOKIE_KEY)
        # 与浏览器cookie中的MD5进行比较。MD5 ?
        if sha1s != hashlib.sha1(s.encode("utf-8")).hexdigest():
            logging.info("invalid sha1")
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None


# use to test
# 响应字典 dict
# @get('/')
# def index_old(request):
#     users = yield from User.findAll()
#     return {
#         '__template__': 'test.html',
#         'users': users
#     }

# @get('/')
# def index(request):
#     summary = 'Lorem ipsum dolor sit amet, ' \
#               'consectetur adipisicing elit, ' \
#               'sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
#     blogs = [
#         Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
#         Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
#         Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
#     ]
#     return {
#         '__template__': 'blogs.html',
#         'blogs': blogs
#     }
# -----------------------------------------用户浏览页面------------------------------------------------
# 对于首页的get请求的处理
@get('/')
def index(*, page="1"):
    page_index = get_page_index(page)
    num = yield from Blog.findNumber("count(id)")
    page = Page(num)
    if num == 0:
        blogs = []
    else:
        blogs = yield from Blog.findAll(orderBy="created_at desc", limit=(page.offset, page.limit))
    # 返回一个字典, 其指示了使用何种模板,模板的内容
    # app.py的response_factory将会对handler的返回值进行分类处理
    return{
        "__template__": "blogs.html",
        "page": page,
        "blogs": blogs  # 参数blogs将在jinja2模板中被解析
    }


@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }


@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }


@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    # 若无前一个网址,可能是用户新打开了一个标签页,则登录后转到首页
    r = web.HTTPFound(referer or '/')
    # 清理掉cookie得用户信息数据
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r


# 博客详情页
@get('/blog/{id}')
def get_blog(id):
    blog = yield from Blog.find(id) # 通过id从数据库拉取博客信息
    # 从数据库拉取指定blog的全部评论,按时间降序排序,即最新的排在最前
    comments = yield from Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    # 将每条评论都转化为html格式(根据text2html代码可知,实际为html的<p>)
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)  # blog是markdown格式,将其转换为html格式
    return {
        # 返回的参数将在jinja2模板中被解析
        "__template__": "blog.html",
        "blog": blog,
        "comments": comments
    }

# -----------------------------------------后端API-----------------------------------------------------
_RE_EMAIL = _RE_EMAIL = re.compile(r'^[a-z0-9\.\-_]+@[a-z0-9\-_]+(\.[a-z0-9\-_]+){1,4}$')
_RE_SHA1 = re.compile(r'[0-9a-f]{40}$')


# API: 获取用户信息
@get('/api/users')
def api_get_users(*, page="1"):
    page_index = get_page_index(page)
    num = yield from User.findNumber("count(id)")
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = yield from User.findAll(orderBy="created_at desc")
    for u in users:
        u.passwd = "*****"
    # 以dict形式返回,并且未指定__template__,将被app.py的response factory处理为json
    return dict(page=p, users=users)


# API: 用户注册
@post('/api/users')
def api_register_user(*, email, name, passwd):
    """
    save in table: USER
    登录之后，可以增加邮箱激活模块，邮件激活。
    """
    logging.info("......................")
    if not name or not name.strip():
        raise APIValueError("name")
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError("email")
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError("passwd")
    users = yield from User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    # 创建用户对象, 其中密码并不是用户输入的密码,而是经过复杂处理后的保密字符串
    # sha1(secure hash algorithm),是一种不可逆的安全算法.
    # hexdigest()函数将hash对象转换成16进制表示的字符串
    # md5是另一种安全算法
    # Gravatar(Globally Recognized Avatar)是一项用于提供在全球范围内使用的头像服务。
    # 便可以在其他任何支持Gravatar的博客、论坛等地方使用它。此处image就是一个根据用户email生成的头像
    user = User(
        id=uid,
        name=name.strip(),
        email=email,
        passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
        # image="http://www.gravatar.com/avatar/%s?d=mm&s=120" % hashlib.md5(email.encode('utf-8')).hexdigest(),
        image="about:blank"
    )
    yield from user.save()
    # 此处的cookie：网站为了辨别用户身份而储存在用户本地终端的数据
    # http协议是一种无状态的协议,即服务器并不知道用户上一次做了什么.服务器通过cookie跟踪用户状态。
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)  # 86400s=24h
    # 修改密码的外部显示为* ?
    user.passwd = '*****'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


# API: 用户登录
@post('/api/authenticate')
def authenticate(*, email, passwd):
    """
    通过邮箱与密码验证登录
    提交之前，可以在本地或者远端进行合法性验证
    """
    if not email:
        raise APIValueError("email", "Invalid email")
    if not passwd:
        raise APIValueError("passwd", "Invalid password")
    users = yield from User.findAll("email=?", [email])
    if len(users) == 0:
        raise APIValueError("email", "Email not exits")
    user = users[0]
    # sha1_passwd = '%s:%s' % (uid, passwd)
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode("utf-8"))
    sha1.update(b":")
    sha1.update(passwd.encode("utf-8"))
    if user.passwd != sha1.hexdigest():
        raise APIValueError("passwd", "Invalid password")
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = "*****"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    return r


# API: 获取单条日志
@get('/api/blogs/{id}')
def api_get_blog(*, id):
    blog = yield from Blog.find(id)
    return blog


# API：创建博客
@post('/api/blogs')
def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name can\'t be empty')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary can\'t be empty')
    if not content or not content.strip():
        raise APIValueError('content', 'content can\'t be empty')
    blog = Blog(
        user_id=request.__user__.id,
        user_name=request.__user__.name,
        user_image=request.__user__.image,
        name=name.strip(),
        summary=summary.strip(),
        content=content.strip(),
        )
    yield from blog.save()
    return blog


# API: 获取blog 列表
@get('/api/blogs')
def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    num = yield from Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = yield from Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)


# API: 修改博客
@post("/api/blogs/{id}")
def api_update_blog(id, request, *, name, summary, content):
    check_admin(request) # 检查用户权限
    # 验证博客信息的合法性
    if not name or not name.strip():
        raise APIValueError("name", "name cannot be empty")
    if not summary or not summary.strip():
        raise APIValueError("summary", "summary cannot be empty")
    if not content or not content.strip():
        raise APIValueError("content", "content cannot be empty")
    blog = yield from Blog.find(id)  # 获取修改前的博客
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    yield from blog.update() # 更新博客
    return blog # 返回博客信息


# API: 删除博客
@post("/api/blogs/{id}/delete")
def api_delete_blog(request, *, id):
    check_admin(request)  # 检查用户权限
    # 根据model类的定义,只有查询才是类方法,其他增删改都是实例方法
    # 因此需要先创建对象,再删除
    blog = yield from Blog.find(id)  # 取出博客
    yield from blog.remove()  # 删除博客
    return dict(id=id)  # 返回被删博客的id


# API: 创建评论
@post('/api/blogs/{id}/comments')
def api_create_comment(id, request,  *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError("Please signin first.")
    # 验证评论内容的存在性
    if not content or not content.strip():
        raise APIValueError("content", "content cannot be empty")
    # 检查博客的存在性
    blog = yield from Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError("Blog", "No such a blog.")
    # 创建评论对象
    comment = Comment(user_id=user.id, user_name=user.name, user_image=user.image, blog_id = blog.id, content=content.strip())
    yield from comment.save() # 储存评论入数据库
    return comment # 返回评论


# API: 删除评论
@post("/api/comments/{id}/delete")
def api_delete_comment(id, request):
    check_admin(request)  # 检查权限
    comment = yield from Comment.find(id)  # 从数据库中取出评论
    if comment is None:
        raise APIResourceNotFoundError("Comment", "No such a Comment.")
    yield from comment.remove()  # 删除评论
    return dict(id=id)  # 返回被删评论的ID


# API: 获取评论
@get("/api/comments")
def api_comments(*, page="1"):
    page_index = get_page_index(page)
    num = yield from Comment.findNumber('count(id)')  # num为评论总数
    p = Page(num, page_index)  # 创建page对象, 保存页面信息
    if num == 0:
        return dict(page=p, comments=())  # 若评论数0,返回字典,将被app.py的response中间件再处理
    # 博客总数不为0,则从数据库中抓取博客
    # limit强制select语句返回指定的记录数,前一个参数为偏移量,后一个参数为记录的最大数目
    comments = yield from Comment.findAll(orderBy="created_at desc", limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)  # 返回字典,以供response中间件处理


# ------------------------------------------------管理页面-------------------------------------
# 写博客的页面
@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }


# 修改博客的页面
@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
    return {
        "__template__": "manage_blog_edit.html",
        'id': id,    # id的值将传给js变量I
        # action的值也将传给js变量action
        # 将在用户提交博客的时候,将数据post到action指定的路径,此处即为创建博客的api
        'action': '/api/blogs/%s' % id
    }


# 管理博客的页面
@get('/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }


# 管理重定向
@get("/manage/")
def manage():
    return "redirect:/manage/comments"


# 管理用户的页面
@get('/manage/users')
def manage_users(*, page='1'):  # 管理页面默认从"1"开始
    return {
        "__template__": "manage_users.html",
        "page_index": get_page_index(page)  # 通过page_index来显示分页
    }


# 管理评论的页面
@get('/manage/comments')
def manage_comments(*, page='1'):  # 管理页面默认从"1"开始
    return {
        "__template__": "manage_comments.html",
        "page_index": get_page_index(page)  # 通过page_index来显示分页
    }


# 管理用户的页面
@get('/manage/users')
def manage_users(*, page='1'):  # 管理页面默认从"1"开始
    return {
        "__template__": "manage_users.html",
        "page_index": get_page_index(page)  # 通过page_index来显示分页
    }