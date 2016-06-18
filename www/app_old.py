#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
async web application.
structure:
asyncio: TCP.   asynhttp: http structure.
"""

import logging
logging.basicConfig(level=logging.INFO)
import asyncio
from aiohttp import web


def index(request):
    return web.Response(body=b'<h1>hello</h1>')


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)
    # access path.
    app.router.add_route('GET', '/', index)
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9999)
    logging.info('server started at http://127.0.0.1:9999...')
    return srv

loop = asyncio.get_event_loop()

# init() is also one coroutine.
loop.run_until_complete(init(loop))
loop.run_forever()