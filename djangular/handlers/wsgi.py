#!/Users/jrief/Workspace/virtualenvs/awesto/bin/uwsgi --virtualenv ~/Workspace/virtualenvs/awesto --http-socket :9090 --gevent 100 --module chat --http-websockets
#!./uwsgi --http-socket :9090 --gevent 100 --module tests.websocket_chat --gevent-monkey-patch
# uwsgi --virtualenv ~/Workspace/virtualenvs/awesto --http :9090 --http-raw-body --gevent 100 --module chat
import sys
import time
import gevent.select
import logging
import redis
from django.http import HttpResponseBadRequest
from django.core.handlers.wsgi import WSGIRequest


logger = logging.getLogger('djangular.wsgi_server')


class WebsocketServer(object):
    def __init__(self, handler):
        self.handler = handler

    def __call__(self, environ, start_request):
        try:
            request = WSGIRequest(environ)
            if request.META.get('HTTP_UPGRADE') != 'websocket':
                return HttpResponseBadRequest('Not a websocket connection')
        except UnicodeDecodeError:
            logger.warning('Bad Request (UnicodeDecodeError)', exc_info=sys.exc_info())
            return HttpResponseBadRequest('UnicodeDecodeError')
        print request
        print 'dir: ', dir(request)

        self.handler.websocket_handshake(request.META['HTTP_SEC_WEBSOCKET_KEY'], request.META.get('HTTP_ORIGIN', ''))
        print "websockets..."
        rcon = redis.StrictRedis(host='localhost', port=6379, db=0)
        channel = rcon.pubsub()
        channel.subscribe('foobar')

        websocket_fd = self.handler.connection_fd()
        redis_fd = channel.connection._sock.fileno()

        while True:
            # wait max 4 seconds to allow ping to be sent
            ready = gevent.select.select([websocket_fd, redis_fd], [], [])
            # send ping on timeout
            if not ready[0]:
                self.handler.websocket_recv_nb()
            for fd in ready[0]:
                if fd == websocket_fd:
                    msg = self.handler.websocket_recv_nb()
                    if msg:
                        rcon.publish('foobar', msg)
                elif fd == redis_fd:
                    msg = channel.parse_response()
                    # only interested in user messages
                    if msg[0] == 'message':
                        self.handler.websocket_send("[%s] %s" % (time.time(), msg))
