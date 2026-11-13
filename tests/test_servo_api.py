"""Isolated parameter contracts. FakeAdapter never connects to an IDE or drive."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('servo_api', ROOT / 'servo_api.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class FakeAdapter:
    def __init__(self, project, args):
        self.identity = {'path': args['path'], 'guid': 'test', 'connector_id': '1'}
        self.entries = [dict(index=0x609A, subindex=0, data_type='UDINT', bit_length=32, writable=True)]
        self.route = 'test-route'
        self.payload = [232, 3, 0, 0]
        self.calls = []
        self.failure = None
        self.read_failure = False
        self.bad_readback = False
        self.last_duration_ms = 1

    def address(self):
        return self.route

    def startup(self):
        return [dict(index=0x609A, subindex=0, value='900')]

    def transfer(self, index, subindex, data=None):
        self.calls.append((index, subindex, data))
        if data is None:
            return {'success': not self.read_failure, 'native_error': 0, 'raw_bytes': list(self.payload)}
        if self.failure:
            return dict(self.failure)
        if not self.bad_readback:
            self.payload = list(data)
        return {'success': True, 'native_error': 0, 'raw_bytes': None}


class ServoApiTests(unittest.TestCase):
    def setUp(self):
        self.original = api.NativeSdo
        self.args = dict(path='Device/EtherCAT/Drive', index=0x609A, subindex=0,
                         data_type='UDINT', value='2000', expected_raw_hex='E8030000', expected_address='test-route')
        self.adapter = FakeAdapter(None, self.args)
        api.NativeSdo = lambda project, args: self.adapter

    def tearDown(self):
        api.NativeSdo = self.original

    def test_integer_endianness_and_exact_64_bit_values(self):
        cases = [('SINT', '-128', '80'), ('USINT', '255', 'FF'), ('INT', '-32768', '0080'),
                 ('UINT', '65535', 'FFFF'), ('DINT', '-2147483648', '00000080'),
                 ('UDINT', '4294967295', 'FFFFFFFF'), ('LINT', '-9223372036854775808', '0000000000000080'),
                 ('ULINT', '18446744073709551615', 'FFFFFFFFFFFFFFFF'), ('BOOL', '1', '01')]
        for kind, value, expected in cases:
            with self.subTest(kind=kind):
                data = api.sdo_encode(value, kind)
                self.assertEqual(api.sdo_hex(data), expected)
                self.assertEqual(api.sdo_decode(data, kind), value)

    def test_float_wire_format(self):
        self.assertEqual(api.sdo_hex(api.sdo_encode('1.5', 'REAL')), '0000C03F')
        self.assertEqual(api.sdo_decode([0, 0, 192, 63], 'REAL'), '1.5')
        self.assertEqual(api.sdo_decode(api.sdo_encode('-2.25', 'LREAL'), 'LREAL'), '-2.25')

    def test_invalid_numbers_never_reach_adapter(self):
        for kind, value in [('USINT', '-1'), ('SINT', '128'), ('BOOL', '2'), ('UDINT', '1.2'),
                            ('ULINT', '18446744073709551616'), ('REAL', 'NaN'), ('LREAL', 'inf')]:
            with self.subTest(kind=kind, value=value), self.assertRaises((ValueError, OverflowError)):
                api.op_online_sdo_write(None, dict(self.args, data_type=kind, value=value))
        self.assertEqual(self.adapter.calls, [])

    def test_read_keeps_online_and_startup_separate(self):
        r = api.op_online_sdo_read(None, self.args)
        self.assertTrue(r['success'])
        self.assertEqual(r['value'], '1000')
        self.assertEqual(r['startup_matches'][0]['value'], '900')
        self.assertEqual(r['scope'], 'online_device')
        self.assertTrue(r['read_at_utc'].endswith('Z'))

    def test_unknown_esi_keeps_raw_bytes(self):
        self.adapter.entries = []
        args = {k: v for k, v in self.args.items() if k != 'data_type'}
        r = api.op_online_sdo_read(None, args)
        self.assertTrue(r['success'])
        self.assertIsNone(r['data_type'])
        self.assertIsNone(r['value'])
        self.assertEqual(r['raw_hex'], 'E8030000')

    def test_decode_size_failure_keeps_evidence(self):
        self.adapter.payload = [1]
        r = api.op_online_sdo_read(None, self.args)
        self.assertTrue(r['success'])
        self.assertIsNone(r['value'])
        self.assertIn('Expected 4 bytes', r['decode_error'])

    def test_startup_failure_does_not_erase_online_read(self):
        def broken(): raise RuntimeError('incomplete startup list')
        self.adapter.startup = broken
        r = api.op_online_sdo_read(None, self.args)
        self.assertTrue(r['online_verified'])
        self.assertIsNone(r['startup_matches'])
        self.assertIn('incomplete', r['startup_error'])

    def test_write_checks_then_sends_once_and_reads_back(self):
        r = api.op_online_sdo_write(None, self.args)
        self.assertTrue(r['success'])
        self.assertTrue(r['write_accepted'])
        self.assertTrue(r['readback_verified'])
        self.assertEqual(r['after']['value'], '2000')
        self.assertEqual([c[2] for c in self.adapter.calls], [None, [208, 7, 0, 0], None])
        self.assertFalse(r['automatic_store_command'])

    def test_stale_bytes_do_not_write(self):
        r = api.op_online_sdo_write(None, dict(self.args, expected_raw_hex='00000000'))
        self.assertFalse(r['success'])
        self.assertFalse(r['write_attempted'])
        self.assertEqual(len(self.adapter.calls), 1)

    def test_wrong_route_or_read_only_esi_do_not_transfer(self):
        with self.assertRaises(ValueError):
            api.op_online_sdo_write(None, dict(self.args, expected_address='another-device'))
        self.adapter.entries[0]['writable'] = False
        with self.assertRaises(ValueError): api.op_online_sdo_write(None, self.args)
        self.assertEqual(self.adapter.calls, [])

    def test_esi_type_and_size_reject_before_transfer(self):
        for kind in ['DINT', 'UINT', 'REAL']:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                api.op_online_sdo_write(None, dict(self.args, data_type=kind))
        self.assertEqual(self.adapter.calls, [])

    def test_unknown_esi_wrong_width_does_not_write(self):
        self.adapter.entries = []
        r = api.op_online_sdo_write(None, dict(self.args, data_type='USINT', value='5'))
        self.assertFalse(r['success'])
        self.assertFalse(r['write_attempted'])
        self.assertIn('decode_error', r['before'])
        self.assertEqual(len(self.adapter.calls), 1)

    def test_one_bit_bool_uses_one_transfer_byte(self):
        self.adapter.entries[0].update(data_type='BOOL', bit_length=1)
        self.adapter.payload = [0]
        r = api.op_online_sdo_write(None, dict(self.args, data_type='BOOL', value='1', expected_raw_hex='00'))
        self.assertTrue(r['success'])
        self.assertEqual(self.adapter.payload, [1])

    def test_pre_read_failure_does_not_write(self):
        self.adapter.read_failure = True
        r = api.op_online_sdo_write(None, self.args)
        self.assertFalse(r['write_attempted'])
        self.assertEqual(len(self.adapter.calls), 1)

    def test_abort_and_unknown_outcome_are_distinct_no_retry(self):
        for code, unknown in [(0x06090030, False), (0, True), (None, True)]:
            with self.subTest(code=code):
                self.adapter.calls = []
                self.adapter.failure = {'success': False, 'native_error': code, 'error': 'native failure'}
                r = api.op_online_sdo_write(None, self.args)
                self.assertFalse(r['success'])
                self.assertTrue(r['write_attempted'])
                self.assertEqual(r['outcome_unknown'], unknown)
                self.assertEqual(len(self.adapter.calls), 2)

    def test_readback_mismatch_does_not_repeat_write(self):
        self.adapter.bad_readback = True
        r = api.op_online_sdo_write(None, self.args)
        self.assertTrue(r['write_accepted'])
        self.assertFalse(r['readback_verified'])
        self.assertFalse(r['success'])
        self.assertEqual(len(self.adapter.calls), 3)

    def test_dictionary_and_startup_are_offline(self):
        self.adapter.entries[0]['name'] = 'Homing acceleration'
        r = api.op_sdo_dictionary(None, dict(self.args, query='homing', limit=1))
        self.assertEqual(r['total'], 1)
        self.assertFalse(r['online_verified'])
        self.assertIsNone(r['next_offset'])
        self.assertEqual(api.op_servo_startup(None, self.args)['scope'], 'offline_project')
        self.assertEqual(self.adapter.calls, [])

    def test_invalid_index_and_missing_write_reference(self):
        for extra in [dict(index=True), dict(index=65536), dict(subindex=256), dict(expected_raw_hex='0'),
                      dict(expected_raw_hex='zz'), dict(expected_address='')]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                api.op_online_sdo_write(None, dict(self.args, **extra))
        self.assertEqual(self.adapter.calls, [])

    def test_exact_paths_do_not_use_recursive_name_fallback(self):
        child = SimpleNamespace(get_name=lambda: 'Drive', get_children=lambda recurse: [])
        root = SimpleNamespace(get_children=lambda recurse: [child])
        self.assertIs(api._sdo_find(root, 'Drive'), child)
        for path in ['Device/Drive', 'Drive/', '/Drive', '']:
            with self.subTest(path=path), self.assertRaises(ValueError): api._sdo_find(root, path)
        root.get_children = lambda recurse: [child, child]
        with self.assertRaises(ValueError): api._sdo_find(root, 'Drive')

    def test_empty_bus_route_is_skipped_for_controller(self):
        bus = SimpleNamespace(get_name=lambda: 'EtherCAT', get_address=lambda: '', get_children=lambda recurse: [])
        plc = SimpleNamespace(get_name=lambda: 'PLC', get_address=lambda: 'route', get_children=lambda recurse: [bus])
        project = SimpleNamespace(get_children=lambda recurse: [plc])
        self.assertIs(api._sdo_controller(project, 'PLC/EtherCAT/Drive'), plc)


class NativeBindingTests(unittest.TestCase):
    def make_adapter(self, *, missing=False, connection_error=False, invoke_error=False, disconnect_error=False, abort=0):
        events = []
        class TypedArray(list):
            def __init__(self, kind, values): super().__init__(values); self.kind = kind
        class ArrayFactory:
            def __getitem__(self, kind): return lambda values: TypedArray(kind, values)
        class Device:
            def SharedConnect(self, owner):
                events.append(('connect', owner))
                if connection_error: raise RuntimeError('gateway unavailable')
            def SharedDisconnect(self, owner):
                events.append(('disconnect', owner))
                if disconnect_error: raise RuntimeError('disconnect failed')
        device = Device()
        class Manager:
            def GetOnlineDevice(self, guid):
                events.append(('get', guid)); return None if missing else device
            def CreateOnlineDevice(self, guid):
                events.append(('create', guid)); return device
        class Method:
            def __init__(self, name): self.Name = name
            def GetParameters(self): return [None] * 6
            def Invoke(self, service, args):
                events.append(('invoke', self.Name, args))
                self_test.assertIs(args[0], device)
                self_test.assertEqual(args[1:4], ['native-slave', 0x609A, 0])
                if invoke_error: raise TimeoutError('native wait failed')
                if self.Name == 'CoESdoRead': args[4] = [232, 3, 0, 0]
                else:
                    self_test.assertEqual(args[4].kind, int)
                    self_test.assertEqual(args[4], [208, 7, 0, 0])
                args[5] = abort
                return abort == 0
        self_test = self
        service = SimpleNamespace(GetType=lambda: SimpleNamespace(GetMethods=lambda: [Method('CoESdoRead'), Method('CoESdoWrite')]))
        adapter = api.NativeSdo.__new__(api.NativeSdo)
        adapter.System = SimpleNamespace(Object=object, Byte=int, UInt16=int, UInt32=int, Array=ArrayFactory(),
            Activator=SimpleNamespace(CreateInstance=lambda _: service))
        adapter.asm = SimpleNamespace(GetType=lambda *args: 'native-service-type')
        adapter.online_manager = Manager()
        adapter.controller = SimpleNamespace(guid='controller-guid')
        adapter.native = 'native-slave'
        return adapter, events

    def test_cold_read_creates_and_connects_native_device(self):
        adapter, events = self.make_adapter(missing=True)
        r = adapter.transfer(0x609A, 0)
        self.assertTrue(r['success'])
        self.assertEqual(r['raw_bytes'], [232, 3, 0, 0])
        self.assertEqual([e[0] for e in events], ['get', 'create', 'connect', 'invoke', 'disconnect'])
        self.assertIs(events[2][1], events[-1][1])

    def test_write_byte_array_and_abort_byref(self):
        adapter, events = self.make_adapter(abort=0x06090030)
        r = adapter.transfer(0x609A, 0, [208, 7, 0, 0])
        self.assertFalse(r['success'])
        self.assertEqual(r['native_error_hex'], '0x06090030')
        self.assertEqual([e[1] for e in events if e[0] == 'invoke'], ['CoESdoWrite'])
        self.assertEqual(events[-1][0], 'disconnect')

    def test_failed_connection_never_submits_a_write(self):
        adapter, events = self.make_adapter(connection_error=True)
        r = adapter.transfer(0x609A, 0, [208, 7, 0, 0])
        self.assertFalse(r['success'])
        self.assertFalse(r['transfer_started'])
        self.assertEqual(r['error_kind'], 'connection_or_setup_failure')
        self.assertNotIn('invoke', [e[0] for e in events])

    def test_invoke_exception_keeps_unknown_outcome_and_disconnects(self):
        adapter, events = self.make_adapter(invoke_error=True)
        r = adapter.transfer(0x609A, 0, [208, 7, 0, 0])
        self.assertTrue(r['transfer_started'])
        self.assertIsNone(r['native_error'])
        self.assertEqual(events[-1][0], 'disconnect')

    def test_disconnect_failure_does_not_erase_transfer_result(self):
        adapter, events = self.make_adapter(disconnect_error=True)
        r = adapter.transfer(0x609A, 0)
        self.assertTrue(r['success'])
        self.assertEqual(r['raw_bytes'], [232, 3, 0, 0])
        self.assertIn('disconnect failed', r['disconnect_error'])


if __name__ == '__main__':
    unittest.main()
