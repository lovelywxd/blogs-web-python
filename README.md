该框架基于aiohttp, aiomysql, asyncio等模块，即在这些模块之上完成的底层封装

任务：Day12-Day16
搞定python-web过程。包括部署，后续工作，日志页面展开。
博客是个人博客，并不是每个人都可以发表博客的那种服务，期望能够每个人都可以发表博客。
故有admin权限，才能进入manage页面。 那么如何获得admin权限?
在Debug开发模式下完成后端所有API、前端所有页面.

python web structure:   总结

nginx<--->webapp<--->mysql

webapp: MVC. 
M Model(web 框架)
-- 后端处理整体框架，接收request，初步处理，交给URL处理函数（control），协助URL完成对数据库操作(数据操作)，接收URL的处理结果，传给viewer数据。
V viewer
-- 包含显示逻辑（template），View最终输出的就是用户看到的HTML。 模板之类的。
C control
-- URL的处理函数，负责业务逻辑，如数据库操作：检查用户名是否存在，取出用户信息等

ORM框架、Web框架、前端视图viewer
ORM 模型的执行过程:
当用户定义一个class User(Model)时，Python解释器首先在当前类User的定义中查找metaclass，如果没有找到，就继续在父类Model中查找metaclass，找到了，就使用Model中定义的metaclass的ModelMetaclass来创建User类，也就是说，metaclass可以隐式地继承到子类，但子类自己却感觉不到。
处理流程：

1. 初始化服务器。 数据库-->web框架（几个factory，handlers注册--添加路径）
2. 处理过程：
获得request（aiohttp）

依次经过几个middleware: logger_factory-->response_factory-->RequestHandler.__call__
其中在response_factory中会调用之前注册: path<--->RequestHandler(app, fn)
RequestHandler(app, fn)存在的目的主要是为了提供统一的接口。

request通过RequestHandler进行信息提取，提取URL可能需要的参数，
然后根据路径调用相应的URL处理函数，并传入从request中提取的参数
然后返回到response_factory中，构造response



几个问题：

1. aysncio模块。协程（coroutine）的使用，关于generator的理解。
2. aiomysql的使用。一个数据库连接池，如何使用，感觉并没有使用.
3. config 文件的使用，将配置文件的内容加载到程序中。还没有加载。 
4. 前端模板引擎jinja2。对jinja2的使用。数据传输格式，json？
5. aiohttp模块 - 基于asyncio的异步http框架
6. uikit框架：CSS框架 构建前端(HTML, JavaScript, CSS)
7. 还是要搞清楚这一套东西 Requesthandler(app,fn)， 从factory到handler
   主要是aiohttp框架。
8. 如何使得用户具有admin权限？改变数据库。没有后台管理界面？？？？？
9. 编写日志创建页，有问题。。。。没有达到预想的交互效果.   ORM 的执行流程




------------------------------jinja2 模板引擎-------------------------------
template engine

前端渲染工具：在模板和实际的HTML中间充当渲染解释的作用。

Environment: template environment setting
Jinja2 使用一个名为Environment的中心对象。这个类的实例用于存储配置、全局对象，并用于从文件系统或其它位置加载模板。
Even if you are creating templates from strings by using the constructor of Template class, an environment is created automatically for you, albeit a shared one.

<python>
from jinja2 import Template
template = Template('hello, {{ name }}!')
template.render(name='wxd')
</python>


loader(加载器)负责从application路径下的templates文件夹中寻找模板,可使用多个加载器
<python>
from jinja2 import Environment, PackageLoader
# 加载模板环境
env = Environment(loader=PackageLoader('yourapplication', 'templates'))   
template = env.get_template('mytemplate.html')   # 取模板
print template.render(the='variables', go='here')   #模板渲染
</python>

PS
更为复杂的模板应用：模板生成的方法与环境
模板继承---template inheritance

Environment:
In some cases however, it’s useful to have multiple environments side by side, if different configurations are in use



前端的构建：
1. 基础的CSS框架（uikit）完成页面布局和基本样式。Query作为操作DOM的JavaScript库。
2. HTML复用的问题：
  （1） include 把模板页面拆分成几部分。
	<html>
    <% include file="inc_header.html" %>
    <% include file="index_body.html" %>
    <% include file="inc_footer.html" %>
	</html>
  （2） 模板继承：父模板中定义一些可替换的block，再编写多个“子模板”，每个子模板都可以只替换父模板定义的block
  	<!-- base.html -->
	<html>
    	<head>
        	<title>{% block title%} 这里定义了一个名为title的block {% endblock %}</title>
    	</head>
    	<body>
        	{% block content %} 这里定义了一个名为content的block {% endblock %}
    	</body>
	</html>
	一旦定义好父模板的整体布局和CSS样式，编写子模板就会非常容易
3. 前端CSS, HTML, JavaScript。
问题：如何生成大量动态的前端页面? 通过后端代码生成，前端还要与后端进行各种交互。

如果在页面上大量使用JavaScript（事实上大部分页面都会），模板方式仍然会导致JavaScript代码与后端代码绑得非常紧密，以至于难以维护。其根本原因在于负责显示的HTML DOM模型与负责数据和交互的JavaScript代码没有分割清楚。  可维护的前端代码。

主要讨论的是前端与后端的结合问题（最好是前端与后端存在分离）：前端显示逻辑中的MVVM模式，后端是MVC模式
1） 字符串拼接，不可维护
2） 前端模板方式。ASP、JSP、PHP等都是用这种模板方式生成前端页面
    <html>
    <head>
        <title>{{ title }}</title>
    </head>
    <body>
        {{ body }}
    </body>
    </html>

MVVM模式
Model View ViewModel模式

Model：业务逻辑和数据
view: 视图显示，显示逻辑
viewModel：将Model的数据负责同步到view中显示出来。 
view <---DataBinding---> viewModel(Model和view双向绑定)


许多成熟的MVVM框架，例如AngularJS，KnockoutJS等。这里选择Vue简单易用的MVVM框架。说的是前端的显示逻辑框架。

双向绑定是MVVM框架最大的作用。借助于MVVM，我们把复杂的显示逻辑交给框架完成。由于后端编写了独立的REST API，所以，前端用AJAX提交表单非常容易，前后端分离得非常彻底。

Vue：view 和 model之间的viewmodel。 初始化Vue时，我们指定3个参数：

el：根据选择器查找绑定的View，这里是#vm，就是id为vm的DOM，对应的是一个<div>标签；

data：JavaScript对象表示的Model，我们初始化为{ name: '', summary: '', content: ''}；

methods：View可以触发的JavaScript函数，submit就是提交表单时触发的函数。

在<form>标签中，用几个简单的v-model，就可以让Vue把Model和View关联起来。<!-- input的value和Model的name关联起来了 --> <input v-model="name" class="uk-width-1-1">

这样做的好处是前端逻辑更清晰， view， viewmodel, model， 这里的mdoel负责与后端进行动态交互，提交或获取数据。

--------------------------------编写 API ----------------------------------
WEB API: REST（Representational State Transfer）风格的软件架构模式

web API直接返回机器能够直接解析的数据，返回的不是HTML

REST就是一种设计API的模式。最常用的数据格式是JSON。由于JSON能直接被JavaScript读取，故以JSON格式编写的REST风格的API具有简单、易读、易用的特点。

由于API就是把Web-App的功能全部封装了。通过API操作数据，可以极大地把前端和后端的代码隔离。使得后端代码易于测试，前端代码编写更简单。


例如：用户登录注册模块
用户注册：HTML内容展示，javascript提交前欲处理，提交至/api/users. register.html
然后存储到数据库中，返回cookie等东西。
后台处理用户注册的函数：@post('/api/users')。
问题：用户注册成功之后呢？前端页面下显示情况？redirect

用户登录模块：
HTTP协议无状态协议，服务器要跟踪用户状态，只能通过cookie实现。大多数web框架提供的Session功能来封装保存用户状态的cookie

Session的优点是简单易用，可以直接从Session中取出用户登录信息。
Session的缺点是服务器需要在内存中维护一个映射表来存储用户登录信息，如果有两台以上服务器，就需要对Session做集群，因此，使用Session的Web App很难扩展。

可通过直接读取cookie的方式验证用户登录，每次访问任意URL，都会对cookie进行验证。这种方式的好处是保证服务器处理任意的URL都是无状态的，可以扩展到多台服务器。

安全性：
由于登录成功后是由服务器生成一个cookie发送给浏览器，所以，要保证这个cookie不会被客户端伪造出来。
实现防伪造cookie的关键是通过一个单向算法（例如SHA1）
SHA1是一种单向算法，即可以通过原始字符串计算出SHA1结果，但无法通过SHA1结果反推出原始字符串。

关于登录和注册过程的用户密码，用户密码都会经过复杂的处理：
本地处理： 
passwd: this.passwd===''?'' : CryptoJS.SHA1(email + ':' + this.passwd).toString()
服务器端存储：
sha1_passwd = '%s:%s' % (uid, passwd)
passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),


------------------------------python aio, generator------------------------





---------------------------------Debug模式下的自动重新加载 watchdog----------------------

Django 下的Debug模式。每次修改文件，自动重新加载程序。

pymonitor.py：实现程序的自动加载。 启动app.py

实现思路：检测www目录下的代码改动，一旦有改动，就自动重启服务器.

启动app.py，并时刻监控www目录下的代码改动，有改动时，
先把当前app.py进程杀掉，再重启，就完成了服务器进程的自动重启。

watchdog：可以利用操作系统的API来监控目录文件的变化，并发送通知

利用Python自带的subprocess实现进程的启动和终止，并把输入输出重定向到当前进程的输入输出中



-----------------------------软链接 web部署----------------------------------------------
linux下的软链接：
www：可以选择指向某个目录，相当于一个虚拟的文件夹，真正表示的文件夹是其所指向的文件目录（实际存储），可以通过改变文件目录实现实际链接（当前运行的版本）。
nginx等配置文件只需要指向WWW即可。
ln -s test test1 （test1: 软链接文件， test：目标文件  test1 -> test）

Fabric 自动化部署工具(本机安装Fabric), 部署到远端服务器上。  
fabfile(类似于Makefile)：fab build，fab deploy（本地开发环境部署到远端服务器上的工具）

web部署：

Nginx（反向代理） --- Supervisor(管理进程的工具) --- app.py

Supervisor是一个管理进程的工具，可以随系统启动而启动服务，它还时刻监控服务进程，如果服务进程意外退出，Supervisor可以自动重启服务



nginx 和 supervisor部署。

# 关于日志问题：不知道为什么，老是在以前的旧路径里面建立，但是在webapp.conf里面，我已经添加了新的路径
# 最后解决办法：修改nginx.conf(主配置文件)里面的access_log path。 注释掉webapp.conf（子配置文件）中的设置，默认日志文件在: /var/log/nginx/{log-name}

# sudo /etc/init.d/nginx reload。    重新加载配置文件  /usr/sbin/nginx

# 第二个遇到的问题是：(./app.py  提示错误。不能运行，原因系统编码)
unix和windows文件格式(系统编码：如行结尾标识（换行符，回车符）)的问题：
转换方法 
1. vi filename      (进入vi命令行)set ff = (unix or windows)
2. linux下直接替换： sed -i 's/^M//g'  filename  注意^M 在linux 下写法 按^M 是回车换行符,输入方法是按住CTRL+v,松开v,按m
3, windows 下转换： 利用一些编辑器如UltraEdit或EditPlus等工具先将脚本编码转换，再放到Linux中执行。转换方式如下（UltraEdit）：File-->Conversions-->DOS->UNIX即可。

# supervisor遇到问题
sudo touch /var/run/supervisor.sock
sudo chmod 777 /var/run/supervisor.sock
sudo service supervisor restart


-------------------------python-web-app 所有页面展示----------------------------------------

后端API包括：

    获取日志：GET /api/blogs

    创建日志：POST /api/blogs

    修改日志：POST /api/blogs/:blog_id

    删除日志：POST /api/blogs/:blog_id/delete

    获取评论：GET /api/comments

    创建评论：POST /api/blogs/:blog_id/comments

    删除评论：POST /api/comments/:comment_id/delete

    创建新用户：POST /api/users

    获取用户：GET /api/users

管理页面包括：

    评论列表页：GET /manage/comments

    日志列表页：GET /manage/blogs

    创建日志页：GET /manage/blogs/create

    修改日志页：GET /manage/blogs/

    用户列表页：GET /manage/users

用户浏览页面包括：

    注册页：GET /register

    登录页：GET /signin

    注销页：GET /signout

    首页：GET /

日志详情页：
    GET /blog/:blog_id
