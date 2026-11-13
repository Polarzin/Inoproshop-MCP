"""Exercise the finite worker with fake native handlers; never starts an IDE."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


class ServoWorkerTests(unittest.TestCase):
    def run_worker(self, outcome='success', operation='read'):
        source = (Path(__file__).resolve().parents[1] / 'worker.py').read_text(encoding='utf-8')
        source = source.rsplit('\ntry:\n    main()', 1)[0]
        saved, closed, called = [], [], []
        project = SimpleNamespace(save=lambda: saved.append(True), close=lambda: closed.append(True))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'owner.json').write_text(json.dumps({'pid': os.getpid()}))
            (root / 'request.json').write_text(json.dumps({'root': folder, 'project': str(root/'synthetic.project'),
                'action': 'servo', 'operation': operation, 'path': 'Device/EtherCAT/Drive', 'index': 24730, 'subindex': 0}))
            (root / 'worker_api.py').write_text('')
            (root / 'servo_api.py').write_text('''
def handler(project, args):
    called.append(args['operation'])
    if outcome == 'exception': raise RuntimeError('native connection failure')
    return {'success': outcome == 'success', 'online_verified': outcome == 'success',
            'scope': 'online_device', 'raw_hex': 'e8030000', 'native_error': 0}
op_online_sdo_read = op_online_sdo_write = op_sdo_dictionary = op_servo_startup = handler
''')
            ns = {'REQUEST_PATH': str(root/'request.json'), 'unicode': str, 'outcome': outcome, 'called': called,
                  'system': SimpleNamespace(), 'PromptHandling': SimpleNamespace(LogSimplePrompts=1),
                  'projects': SimpleNamespace(open=lambda *args: project)}
            exec(compile(source, 'worker.py', 'exec'), ns)
            ns['main']()
            result = json.loads((root/'result.json').read_text())
        self.assertEqual(saved, [])
        self.assertEqual(closed, [True])
        self.assertEqual(called, [operation])
        return result

    def test_read_does_not_save(self):
        result = self.run_worker()
        self.assertTrue(result['ok'])
        self.assertTrue(result['online_verified'])
        self.assertEqual(result['servo']['raw_hex'], 'e8030000')

    def test_native_failure_preserves_receipt(self):
        result = self.run_worker('failure')
        self.assertFalse(result['ok'])
        self.assertFalse(result['online_verified'])
        self.assertEqual(result['servo']['native_error'], 0)

    def test_write_does_not_save_or_repeat(self):
        for outcome in ('success', 'failure', 'exception'):
            with self.subTest(outcome=outcome):
                result = self.run_worker(outcome, operation='write')
                self.assertEqual(result['ok'], outcome == 'success')

    def test_exception_does_not_save(self):
        result = self.run_worker('exception')
        self.assertFalse(result['ok'])
        self.assertIn('native connection failure', result['error'])


if __name__ == '__main__':
    unittest.main()
