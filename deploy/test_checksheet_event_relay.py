import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from urllib.error import HTTPError

from checksheet_event_relay import EventRelay


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, *_):
        return b'{"ok":true}'


class RelayTest(unittest.TestCase):
    def test_delivery_retries_survive_restart_without_changing_analytics_outbox(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'machine.db'
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE outbox_events(event_id TEXT PRIMARY KEY,event_type TEXT,line_code TEXT,shift_id TEXT,occurred_at TEXT,payload_json TEXT,status TEXT)')
            for line in ('ABB2', 'ABB3', 'ABB7'):
                db.execute('INSERT INTO outbox_events VALUES(?,?,?,?,?,?,?)', (line + '-event', 'reject.recorded', line, 'shift-' + line, '2026-10-23T00:00:00Z', '{"ng_quantity":2}', 'SENT'))
            db.commit()
            received = []

            def failing(req, **_):
                raise HTTPError(req.full_url, 503, 'Unavailable', {}, None)

            relay = EventRelay(path, 'ABB3', 'http://ai-pc/api/integrations/events', 'private-token', opener=failing)
            self.assertFalse(relay.deliver_one(now=100))
            relay.close()

            def success(req, **_):
                received.append(json.loads(req.data))
                self.assertEqual(req.get_header('Authorization'), 'Bearer private-token')
                return Response()

            relay = EventRelay(path, 'ABB3', 'http://ai-pc/api/integrations/events', 'private-token', opener=success)
            self.assertFalse(relay.deliver_one(now=101), 'retry delay is persisted')
            self.assertTrue(relay.deliver_one(now=103))
            self.assertFalse(relay.deliver_one(now=104), 'acknowledged events never replay')
            self.assertEqual(received, [{'event_id': 'ABB3-event', 'event_type': 'reject.recorded', 'line_code': 'ABB3', 'shift_id': 'shift-ABB3', 'occurred_at': '2026-10-23T00:00:00Z', 'payload': {'ng_quantity': 2}}])
            self.assertEqual(db.execute('SELECT status FROM outbox_events').fetchall(), [('SENT',)] * 3)
            relay.close()
            # Separate line relays can read the same schema without consuming each other's events.
            for line in ('ABB2', 'ABB7'):
                relay = EventRelay(path, line, 'http://ai-pc/api/integrations/events', 'private-token', opener=success)
                self.assertTrue(relay.deliver_one(now=105))
                relay.close()
            self.assertEqual([event['line_code'] for event in received], ['ABB3', 'ABB2', 'ABB7'])
            db.close()

    def test_invalid_configuration_does_not_create_a_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'missing.db'
            with self.assertRaises(ValueError):
                EventRelay(path, 'ABB4', 'http://ai-pc/events', 'token')
            with self.assertRaises(ValueError):
                EventRelay(path, 'ABB3', 'http://ai-pc/events', '')
            with self.assertRaises(sqlite3.OperationalError):
                EventRelay(path, 'ABB3', 'http://ai-pc/events', 'token')
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
