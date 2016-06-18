#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORM,建立类与数据库表的映射
ORM通过打开数据库连接,再由连接创建游标,通过游标执行一系列操作
将符合数据库表的格式的数据插入,或更新或其他操作,而实现类与数据库的映射的.
"""
# 处理数据库部分
# 数据库：用户信息，评论，日志。多个表，多个连接。
# 数据库操作。 处理数据库事务。
import asyncio
import aiomysql
import logging
logging.basicConfig(level=logging.INFO)


def log(sql, args=()):
    logging.info('SQL: %s ' % sql)


# 创建全局连接池  loop没太懂
# 连接池始终存在连接可用，每次用户连接数据库，不需要再重复建立连接。即复用连接？
@asyncio.coroutine
def create_pool(loop, **kwargs):
    logging.info('create database connection pool...')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host=kwargs.get('host', 'localhost'),
        port=kwargs.get('port', 3306),
        user=kwargs['user'],
        password=kwargs['password'],
        db=kwargs['db'],
        charset=kwargs.get('charset', 'utf8'),
        autocommit=kwargs.get('autocommit', True),
        maxsize=kwargs.get('maxsize', 10),
        minsize=kwargs.get('minsize', 1),
        loop=loop
    )


# =============================SQL处理函数区==========================
# SQL语句中的占位符，防止SQL注入攻击?
@asyncio.coroutine
def select(sql, args, size=None):
    log(sql, args)
    global __pool
    with (yield from __pool) as conn:
        # DictCursor: A cursor which returns results as a dictionary. 返回的结果均为字典
        cur = yield from conn.cursor(aiomysql.DictCursor)
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returned: %s' % len(rs))
        return rs

    # async with __pool.get() as conn:
    #         try:
    #             async with conn.cursor(aiomysql.DictCursor) as cur:
    #                 await cur.execute(sql.replace('?', '%s'), args or ())
    #                 if size:
    #                     rs = await cur.fetchmany(size)
    #                 else:
    #                     rs = await cur.fetchall()
    #         except BaseException as e:
    #             rs = []
    #             logger.info(e)
    #         logger.info('rows returned: %s' % len(rs))
    #         return rs
    # insert into `users`( `admin`, `image`, `name`, `passwd`, `create_at`, `email`, `id`) values(False, 'about:blank', 'test', 'test', 1465052585.082479, 'test@example.com', None);


@asyncio.coroutine
def execute(sql, args, autocommit=True):
    log(sql,args)
    logging.info(args)
    # 异步等待连接池对象返回可用连接
    with (yield from __pool) as conn:
        try:
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?', '%s'), args)
            affected = cur.rowcount
            # yield from cur.close()
            if not autocommit:
                yield from conn.commit()
        except BaseException as e:
            if not autocommit:
                yield from conn.rollback()
            raise e
        return affected


# ========================================数据库字段属性类================================
# 最后那个default字段是什么意思？   如果存在default，在getValueOrDefault中会被用到
class Field(object):
    def __init__(self, name, column_type, primarykey, default):
        self.name = name
        self.column_type = column_type
        self.primarykey = primarykey
        self.default = default

    def __str__(self):
        return '<%s, %s, %s>' % (self.__class__.__name__, self.column_type, self.name)


class StringField(Field):
    def __init__(self, name=None, primarykey=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primarykey, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):
    def __init__(self, name=None, primarykey=False, default=0):
        super().__init__(name, 'bigint', primarykey, default)


class FloatField(Field):
    def __init__(self, name=None, primarykey=False, default=0.0):
        super().__init__(name, 'real', primarykey, default)


class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


# ========================================Model基类以及具其元类=====================
# 任何继承自Model的类（比如User），会自动通过ModelMetaclass扫描映射关系
class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        logging.info("ssssssssssssssssssssssssssssssssss")
        logging.info(name)
        # 排除Model这个基类。即创建Model类不用根据ModelMetaclass修改。
        if name == 'Model':
            logging.info("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            return type.__new__(cls, name, bases, attrs)
        # 获取table名称，一般就是Model类（用户类）的类名
        table_name = attrs.get('__table__', None) or name  # 前面get失败了就直接赋值name
        logging.info('found model: %s (table: %s)' % (name, table_name))
        mappings = dict()
        fields = []
        primary_key = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('found mapping: %s ===> %s' % (k, v))
                mappings[k] = v
                if v.primarykey:
                    if primary_key:
                        raise RuntimeError(
                            'Duplicate primary key for field: %s' % k
                        )
                    primary_key = k
                else:
                    fields.append(k)
        if not primary_key:
            raise RuntimeError('Primary key not fund.')
        for k in mappings.keys():
            attrs.pop(k)
        # %s占位符全部替换成具体的属性名 ?? 需要理解这种写法.奇葩` `
        # solution: 通常情况不需要` ，但是遇到字段名字和sql关键字同名时就需要了
        # fields中的值都是字符串，下面这个匿名函数的作用是在字符串两边加上` `生成一个新的字符串
        # map() 函数操作
        escaped_fields = list(map(lambda f: r" `%s`" % f, fields))

        attrs['__mappings__'] = mappings
        attrs['__table__'] = table_name
        attrs['__primary_key__'] = primary_key
        attrs['__fields__'] = fields
        # 构造默认的SELECT, INSERT, UPDATE 和 DELETE语句
        # 其实也可放到Model中去封装这几个函数。
        attrs['__select__'] = 'select `%s`, %s from `%s`' % \
                              (primary_key, ','.join(escaped_fields), table_name)
        attrs['__insert__'] = 'insert into `%s`(%s, `%s`) values(%s)' % \
                              (table_name, ','.join(escaped_fields), primary_key, create_args_string(len(escaped_fields)+1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % \
                              (table_name, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primary_key)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' \
                              % (table_name, primary_key)
        return type.__new__(cls, name, bases, attrs)


# ？ SQL 语句中的参数值。 field为字段名。
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)


class Model(dict, metaclass=ModelMetaclass):
    logging.info("zzzzzzzzzzzzzzzzzzzzzzzzzz")
    def __init__(self, **kw):
        logging.info("ttttttttttttttttttttttttttt")
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        # 关于getattr(). 反射：根据字符串获取方法实例。透明类：方法和属性
        # self[key]
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        logging.info(key)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                # why?  如果没有这个属性，添加属性
                setattr(self, key, value)
        return value

    # -------------------------------SQL操作-----------------------------------
    @classmethod
    @asyncio.coroutine
    def findAll(cls, where=None, args=None, **kw):
        """
        find object by where clause
        """
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = yield from select(' '.join(sql), args)
        # fetchall return list.  cls(**r). why? 元素为dict类型的。
        # 均为字典类型的元素 继承了dict
        # 从数据库返回为包含字典类型的列表，然后处理为结果： 字段对应结果，感觉是类中各个字段属性复制。
        return [cls(**r) for r in rs]

    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        """
        find object by primary key.
        """
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        """
        find number by select and where.
        """
        sql = ['select %s _num_ from `%s` ' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @asyncio.coroutine
    def save(self):
        """
        arg是保存所有Model实例属性和主键的list,
        使用getValueOrDefault方法的好处是保存默认值.比如id等系统默认生成的字段值
        """
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        logging.info(self.__insert__)
        logging.info(args)
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            logging.warn(
                'failed to insert record: affected rows: %s' % rows
            )

    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__update__, args)
        if rows != 1:
            logging.warn(
                'failed to update by primary key: affected rows: %s' % rows
            )

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warn(
                'failed to remove by primary key: affected rows: %s' % rows
            )

