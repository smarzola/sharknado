import json
import motor
from bson import ObjectId
from collections import OrderedDict
from datetime import datetime, timedelta
from pymongo import ASCENDING, DESCENDING
from tornado import gen, escape
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.options import parse_command_line, define, options
from tornado.web import RequestHandler, Application, url
from urlparse import urlparse


define("port", default='8000')
define("processes", default=1)
define("mongo_uri", default=None)
define("events_expire", default=3600 * 24 * 30)
define("cors_origin", default="*")


def make_mongo_db():
    uri = options.mongo_uri
    try:
        _dbname = urlparse(uri).path[1:]
    except:
        _dbname = 'sharknado'

    _connection = motor.MotorClient(uri)
    db = _connection[_dbname]

    events_expire = int(options.events_expire)
    if events_expire:
        db.events.ensure_index('created', expireAfterSeconds=events_expire)
    db.events.ensure_index([('name', ASCENDING), ('created', DESCENDING)])
    db.counters.ensure_index('name')
    return db


class MongoEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super(MongoEncoder, self).default(o)


def json_encode(value):
    return json.dumps(value, cls=MongoEncoder)


escape.json_encode = json_encode


def make_evt_response(action, things, status='succeeded'):
    return OrderedDict((('this', status),
                        ('by', action),
                        ('the', 'events'),
                        ('with', things)))


def parse_args(args):
    return {name: (arg[0] if len(arg) == 1 else arg) for name, arg in args.iteritems()}


class CorsRequestHandler(RequestHandler):
    def set_default_headers(self):
        if self.request.headers.get('Origin') and options.cors_origin:
            self.set_header('Access-Control-Allow-Origin', options.cors_origin)


class SendEvent(CorsRequestHandler):
    @gen.coroutine
    def get(self, name):
        content = parse_args(self.request.arguments)
        event = yield self.store_event(name, content)
        self.write(make_evt_response('sending', event))

    @gen.coroutine
    def post(self, name):
        try:
            content = json.loads(self.request.body)
        except Exception as e:
            self.write(make_evt_response('sending', {'error': str(e)}, status='failed'))
        else:
            event = yield self.store_event(name, content)
            self.write(make_evt_response('sending', event))

    @gen.coroutine
    def store_event(self, name, content):
        db = self.settings['db']
        event = {'thing': name, 'created': datetime.utcnow(), 'content': content}
        event['_id'] = yield db.events.insert(event)
        yield db.counters.update({'thing': name}, {'$inc': {'count': 1}}, upsert=True)
        raise gen.Return(event)


class GetEvents(CorsRequestHandler):
    def initialize(self, limit=None):
        self.limit = limit

    @gen.coroutine
    def get(self, name, days=30):
        db = self.settings['db']
        after = datetime.utcnow() - timedelta(days=int(days))
        events = yield db.events.find({'thing': name, 'created': {'$gte': after}}) \
            .sort('created', DESCENDING).to_list(self.limit)
        self.write(make_evt_response('getting', events))


class CountEvents(CorsRequestHandler):
    @gen.coroutine
    def get(self, name):
        db = self.settings['db']
        counter = yield db.counters.find_one({'thing': name}, fields={'_id': False})
        self.write(make_evt_response('counting', counter))


def make_app():
    return Application([url(r"/send/event/for/([^/]+)/?", SendEvent),
                        url(r"/get/latest/event/for/([^/]+)/?", GetEvents, dict(limit=1)),
                        url(r"/get/events/for/([^/]+)/?", GetEvents),
                        url(r"/get/events/for/([^/]+)/past/([0-9]+)-days?", GetEvents),
                        url(r"/count/events/for/([^/]+)/?", CountEvents)])


def main():
    parse_command_line()
    app = make_app()
    server = HTTPServer(app)
    server.bind(int(options.port))
    server.start(int(options.processes))
    app.settings['db'] = make_mongo_db()
    IOLoop.current().start()


if __name__ == '__main__':
    main()
