from collections import namedtuple
import json
import sharknado
import unittest
import urllib
from bson import ObjectId
from datetime import datetime, timedelta
from tornado import escape, gen
from tornado.ioloop import IOLoop
from tornado.testing import AsyncHTTPTestCase


class TestHelpers(unittest.TestCase):
    def test_mongo_encoder_datetime(self):
        now = datetime.utcnow()
        data = {'now': now}
        json_data = sharknado.MongoEncoder().encode(data)
        self.assertEqual(now.isoformat(), json.loads(json_data)['now'])

    def test_mongo_encoder_objectid(self):
        _id = ObjectId()
        data = {'_id': _id}
        json_data = sharknado.MongoEncoder().encode(data)
        self.assertEqual(str(_id), json.loads(json_data)['_id'])

    def test_tornado_encoder_patch(self):
        self.assertEqual(sharknado.json_encode, escape.json_encode)

    def test_evt_response_content(self):
        expected = {'this': 'succeeded', 'by': 'testing', 'the': 'messages', 'with': ['spam', 'egg']}
        result = sharknado.make_evt_response(expected['by'], expected['with'], expected['this'])
        self.assertDictEqual(expected, result)

    def test_evt_response_order(self):
        expected_items = [('this', 'succeeded'), ('by', 'testing'), ('the', 'messages'), ('with', ['spam', 'egg'])]
        expected = dict(expected_items)
        result = sharknado.make_evt_response(expected['by'], expected['with'], expected['this'])
        self.assertEqual(expected_items, result.items())

    def test_args_parser(self):
        args = {'ham': ['ham'], 'spamegg': ['spam', 'egg']}
        parsed = sharknado.parse_args(args)
        self.assertEqual({'ham': 'ham', 'spamegg': ['spam', 'egg']}, parsed)


class TestServices(AsyncHTTPTestCase):
    def setUp(self):
        self._options = sharknado.options
        sharknado.options = namedtuple('Options', ['mongo_uri', 'messages_expire', 'cors_origin'])._make(
            ['mongodb://localhost:27017/sharknado_test', 0, '*'])
        self.db = sharknado.make_mongo_db()
        super(TestServices, self).setUp()

    def tearDown(self):
        sharknado.options = self._options
        self.db.connection.drop_database(self.db.delegate.name)
        super(TestServices, self).tearDown()

    def get_app(self):
        app = sharknado.make_app()
        app.settings['db'] = self.db
        return app

    def get_new_ioloop(self):
        return IOLoop.instance()

    def _get(self, url, params=None, **kwargs):
        if params:
            url += ('?%s' % urllib.urlencode(params))
        return self.fetch(url, **kwargs)

    def test_send_empty_message(self):
        resp = self._get('/send/message/for/test')
        self.assertDictContainsSubset({'content': {}, 'thing': 'test'}, json.loads(resp.body)['with'])

        @gen.coroutine
        def check_count():
            count = yield self.db.messages.count()
            self.assertEqual(1, count)

        self.io_loop.run_sync(check_count)

    def test_send_message_with_data(self):
        params = {'spam': 'egg'}
        resp = self._get('/send/message/for/test', params=params)
        self.assertEqual(params, json.loads(resp.body)['with']['content'])

        @gen.coroutine
        def check_stored():
            stored = yield self.db.messages.find_one()
            self.assertEqual(params, stored['content'])

        self.io_loop.run_sync(check_stored)

    def test_send_message_json_body(self):
        params = {'spam': 'egg'}
        resp = self.fetch('/send/message/for/test', method='POST', body=json.dumps(params))
        self.assertEqual(params, json.loads(resp.body)['with']['content'])

    def test_send_message_formencoded_failure(self):
        params = {'spam': 'egg'}
        resp = self.fetch('/send/message/for/test', method='POST', body=urllib.urlencode(params))
        self.assertEqual('failed', json.loads(resp.body)['this'])

    def test_get_latest_message(self):
        latest_params = None
        for idx in range(3):
            latest_params = {'spam': 'egg_%d' % idx}
            self._get('/send/message/for/test', params=latest_params)
        resp = self._get('/get/latest/message/for/test')
        resp_json = json.loads(resp.body)
        self.assertEqual(1, len(resp_json['with']))
        self.assertEqual(latest_params, resp_json['with'][0]['content'])

    def test_get_all_messages(self):
        latest_params = None
        for idx in range(3):
            latest_params = {'spam': 'egg_%d' % idx}
            self._get('/send/message/for/test', params=latest_params)
        resp = self._get('/get/messages/for/test')
        resp_json = json.loads(resp.body)
        self.assertEqual(3, len(resp_json['with']))
        self.assertEqual(latest_params, resp_json['with'][0]['content'])

    def test_filter_message_days(self):
        @gen.coroutine
        def store_messages():
            delta_days = [1, 1, 2, 3, 5, 8]
            for days in delta_days:
                created = datetime.utcnow() - timedelta(days=days)
                message = {'thing': 'test', 'created': created, 'content': {}}
                yield self.db.messages.insert(message)

        self.io_loop.run_sync(store_messages)

        resp = self._get('/get/messages/for/test/past/4-days')
        self.assertEqual(4, len(json.loads(resp.body)['with']))

        resp = self._get('/get/messages/for/test/past/7-day')
        self.assertEqual(5, len(json.loads(resp.body)['with']))

    def test_default_filter_30_days(self):
        @gen.coroutine
        def store_messages():
            message = {'thing': 'test', 'created': datetime.utcnow(), 'content': {}}
            yield self.db.messages.insert(message)
            message = {'thing': 'test', 'created': datetime.utcnow() - timedelta(days=31), 'content': {}}
            yield self.db.messages.insert(message)

        self.io_loop.run_sync(store_messages)

        resp = self._get('/get/messages/for/test')
        self.assertEqual(1, len(json.loads(resp.body)['with']))

    def test_message_counter(self):
        for _ in range(3):
            self._get('/send/message/for/test')

        resp = self._get('/count/messages/for/test')
        self.assertEqual(3, json.loads(resp.body)['with']['count'])

    def test_cors(self):
        resp = self._get('/send/message/for/test', headers={'Origin': 'localhost'})
        self.assertEqual('*', resp.headers['Access-Control-Allow-Origin'])
