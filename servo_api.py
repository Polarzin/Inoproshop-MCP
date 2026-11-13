# -*- coding: utf-8 -*-
"""EtherCAT parameters through the locally installed InoProShop 1.9.1.6 plugin.

Usable as a module or beside worker_api.py. No vendor code or device descriptions
are bundled. Reads never save or download the project.
"""
import datetime
import math
import struct
import os
import re
import time

try:
    basestring
except NameError:
    basestring, unicode, long = str, str, int


def _sdo_find(project, path):
    if not isinstance(path, basestring) or not path or any(not p for p in path.split('/')):
        raise ValueError('An exact slash-separated device path is required')
    current = project
    for part in path.split('/'):
        matches = [c for c in current.get_children(False) if c.get_name() == part]
        if len(matches) != 1:
            raise ValueError('Object path missing or ambiguous: %s' % path)
        current = matches[0]
    return current


def _sdo_int(args, name, default, minimum, maximum=None):
    value = args.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, long)):
        raise ValueError('%s must be an integer' % name)
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError('%s out of range' % name)
    return value


def _sdo_controller(project, path):
    # ScriptEngine exposes get_address on bus nodes too; skip empty bus routes.
    parts = path.split('/')
    for n in range(len(parts) - 1, 0, -1):
        parent = _sdo_find(project, '/'.join(parts[:n]))
        if hasattr(parent, 'get_address') and unicode(parent.get_address() or ''):
            return parent
    return None


SDO_SCALARS = {
    'BOOL': (1, False), 'SINT': (1, True), 'USINT': (1, False),
    'INT': (2, True), 'UINT': (2, False), 'DINT': (4, True), 'UDINT': (4, False),
    'LINT': (8, True), 'ULINT': (8, False), 'REAL': (4, None), 'LREAL': (8, None),
    'BYTE': (1, False), 'WORD': (2, False), 'DWORD': (4, False), 'LWORD': (8, False),
}


def sdo_hex(data):
    return ''.join('%02X' % int(b) for b in data)


def sdo_decode(data, data_type):
    """Return exact decimal strings; never round 64-bit integers through JSON floats."""
    if data_type not in SDO_SCALARS:
        raise ValueError('Unsupported scalar data_type: %s' % data_type)
    size, signed = SDO_SCALARS[data_type]
    if len(data) != size:
        raise ValueError('Expected %d bytes for %s; received %d' % (size, data_type, len(data)))
    if signed is None:
        raw = struct.pack('%dB' % size, *data)
        value = struct.unpack('<f' if size == 4 else '<d', raw)[0]
        if math.isnan(value) or math.isinf(value):
            raise ValueError('Non-finite floating point value')
        return repr(value)
    value = sum(int(b) << (8 * i) for i, b in enumerate(data))
    if signed and value & (1 << (size * 8 - 1)):
        value -= 1 << (size * 8)
    if data_type == 'BOOL' and value not in (0, 1):
        raise ValueError('BOOL payload must be 0 or 1')
    return unicode(value)


def sdo_encode(value, data_type):
    if data_type not in SDO_SCALARS or not isinstance(value, basestring):
        raise ValueError('A supported data_type and a string value are required')
    size, signed = SDO_SCALARS[data_type]
    if signed is None:
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            raise ValueError('value must be finite')
        packed = struct.pack('<f' if size == 4 else '<d', number)
        return list(struct.unpack('%dB' % size, packed))
    if not re.match(r'^-?[0-9]+\Z', value):
        raise ValueError('Integer value must be a decimal string')
    number = long(value)
    minimum = -(1 << (size * 8 - 1)) if signed else 0
    maximum = (1 << (size * 8 - (1 if signed else 0))) - 1
    if data_type == 'BOOL':
        maximum = 1
    if not minimum <= number <= maximum:
        raise ValueError('value is outside the %s range' % data_type)
    return [(number >> (8 * i)) & 255 for i in range(size)]


def sdo_address(args):
    return (_sdo_int(args, 'index', None, 1, 65535),
            _sdo_int(args, 'subindex', None, 0, 255))


def sdo_entry(item):
    return {'index': int(item.uiIndex), 'subindex': int(item.usSubIndex),
            'name': unicode(item.sName or ''), 'data_type': unicode(item.sDataType or '').upper(),
            'bit_length': int(item.uiSize), 'access': unicode(item.sFlags or ''),
            'writable': bool(item.bIsWritable), 'default_value': item.sDefaultValue,
            'unit': None, 'unit_source': None, 'source': 'installed_esi'}


class NativeSdo(object):
    """Small adapter for the OEM CoE service; only explicit transfers go online."""
    def __init__(self, project, args):
        import System
        from System.Reflection import BindingFlags
        self.System = System
        self.obj = _sdo_find(project, args['path'])
        if not self.obj.is_device:
            raise ValueError('Selected object is not a device')
        identity = self.obj.get_device_identification()
        self.identity = {'path': args['path'], 'guid': unicode(self.obj.guid),
                         'connector_id': unicode(args.get('connector_id', '1')),
                         'device': {'id': unicode(identity.id), 'type': int(identity.type), 'version': unicode(identity.version)}}
        base = os.path.abspath(os.path.join(System.AppDomain.CurrentDomain.BaseDirectory, '..', 'PlugIns'))
        def assembly(name, folder, version):
            loaded = [a for a in System.AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == name]
            a = loaded[0] if loaded else System.Reflection.Assembly.LoadFrom(os.path.join(base, folder, version, name + '.dll'))
            if unicode(a.GetName().Version) != version:
                raise ValueError('SDO adapter requires %s %s' % (name, version))
            return a
        self.asm = assembly('InoDeviceEditorEthercat.plugin', 'c5bdca6d-c11c-4f98-ac32-585bd063cd98', '1.9.1.6')
        esi_asm = assembly('DeviceEditorEthercat.plugin', '016ce8b2-c18d-4f78-aecc-6f3bcf7d8aa5', '3.5.11.10')
        flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic
        env = self.asm.GetType('Inovance.InoPro.InoDeviceEditorEthercat.APEnvironment', True)
        mgr = env.GetProperty('ObjectMgr', flags).GetValue(None, None)
        self.online_manager = env.GetProperty('OnlineMgr', flags).GetValue(None, None)
        self.native = mgr.GetObjectToRead(project.handle, self.obj.guid).Object
        connectors = [c for c in self.native.Connectors if unicode(c.ConnectorId) == self.identity['connector_id']]
        if len(connectors) != 1 or int(connectors[0].ModuleType) != 65:
            raise ValueError('Expected one EtherCAT slave connector (module_type 65)')
        self.connector = connectors[0]
        self.helper = System.Activator.CreateInstance(esi_asm.GetType('_3S.CoDeSys.Ethercat.XMLFileHelper', True),
                                                      System.Array[System.Object]([self.native]))
        self.helper.CreateObjectDirectoryFromXML()
        prop = self.helper.GetType().GetProperty('SdoArray', BindingFlags.Instance | BindingFlags.NonPublic)
        self.entries = [sdo_entry(x) for group in (prop.GetValue(self.helper, None) or []) for x in group]
        # The selected slave's nearest addressable ancestor owns its communication route.
        self.controller = _sdo_controller(project, args['path'])

    def address(self):
        if self.controller is None:
            raise ValueError('No addressable controller ancestor for the selected slave')
        address = unicode(self.controller.get_address() or '')
        if not address:
            raise ValueError('Controller communication address is not configured')
        return address

    def startup(self):
        self.helper.LoadSDOFromConfig(self.connector)
        rows = [{'index': int(x.uiIndex), 'subindex': int(x.usSubIndex), 'bit_length': int(x.uiSize),
                 'value': unicode(x.sValue), 'name': unicode(x.sName), 'transition': unicode(x.sTransition),
                 'complete_access': bool(x.bCompleteAccess), 'read_only': bool(x.bReadOnly)}
                for x in self.helper.GetSDOList]
        count = self.connector.HostParameterSet.GetParameter(1627389952)
        if len(rows) != (int(count.Value) if count is not None else 0):
            raise ValueError('Native parser did not read every configured startup entry')
        return rows

    def transfer(self, index, subindex, data=None):
        System = self.System
        started = time.time()
        device, owner, connected, submitted = None, System.Object(), False, False
        receipt = {}
        try:
            device = self.online_manager.GetOnlineDevice(self.controller.guid)
            if device is None:
                device = self.online_manager.CreateOnlineDevice(self.controller.guid)
            device.SharedConnect(owner)
            connected = True
            service = System.Activator.CreateInstance(self.asm.GetType('Inovance.InoPro.InoDeviceEditorEthercat.EthercatService', True))
            name = 'CoESdoRead' if data is None else 'CoESdoWrite'
            method = next(m for m in service.GetType().GetMethods() if m.Name == name and len(m.GetParameters()) == 6)
            payload = None if data is None else System.Array[System.Byte](data)
            args = System.Array[System.Object]([device, self.native, System.UInt16(index), System.Byte(subindex), payload, System.UInt32(0)])
            submitted = True
            accepted = bool(method.Invoke(service, args))
            code = int(args[5])
            receipt = {'success': accepted and code == 0, 'native_return': accepted, 'transfer_started': True,
                    'raw_bytes': [int(x) for x in (args[4] or [])] if data is None else None,
                    'native_error': code, 'native_error_hex': '0x%08X' % code,
                    'error': None if accepted and not code else 'Native SDO transfer failed',
                    'error_kind': None if accepted and not code else ('sdo_abort' if code else 'native_failure_without_code')}
            return receipt
        except Exception as exc:
            inner = exc.GetBaseException() if hasattr(exc, 'GetBaseException') else exc
            receipt = {'success': False, 'native_error': None, 'raw_bytes': None, 'transfer_started': submitted,
                    'error': unicode(inner), 'error_kind': 'native_exception' if submitted else 'connection_or_setup_failure'}
            return receipt
        finally:
            if connected:
                try:
                    device.SharedDisconnect(owner)
                except Exception as exc:
                    receipt['disconnect_error'] = unicode(exc)
            # Release only this call's connection owner. Never retry a failed transfer.
            self.last_duration_ms = int((time.time() - started) * 1000)


def sdo_metadata(adapter, index, subindex):
    matches = [e for e in adapter.entries if e['index'] == index and e['subindex'] == subindex]
    if len(matches) > 1:
        raise ValueError('Ambiguous ESI object definition')
    return matches[0] if matches else None


def sdo_read_result(adapter, args):
    index, subindex = sdo_address(args)
    metadata = sdo_metadata(adapter, index, subindex)
    data_type = args.get('data_type') or (metadata or {}).get('data_type') or None
    result = dict(adapter.identity, index=index, subindex=subindex, scope='online_device',
                  configured_address=adapter.address(), metadata=metadata, data_type=data_type,
                  type_source='caller' if args.get('data_type') else ('installed_esi' if data_type else None))
    result.update(adapter.transfer(index, subindex))
    result.update(read_at_utc=datetime.datetime.utcnow().isoformat() + 'Z',
                  duration_ms=adapter.last_duration_ms, online_verified=result['success'])
    result['raw_hex'] = sdo_hex(result['raw_bytes']) if result.get('raw_bytes') is not None else None
    result['value'] = None
    if result['success'] and data_type:
        try:
            result['value'] = sdo_decode(result['raw_bytes'], data_type)
        except ValueError as exc:
            result['decode_error'] = unicode(exc)
    try:
        result['startup_matches'] = [x for x in adapter.startup() if x['index'] == index and x['subindex'] == subindex]
    except Exception as exc:
        result['startup_matches'] = None
        result['startup_error'] = unicode(exc)
    return result


def op_online_sdo_read(project, args):
    sdo_address(args)
    if args.get('data_type') and args['data_type'] not in SDO_SCALARS:
        raise ValueError('Unsupported scalar data_type')
    return sdo_read_result(NativeSdo(project, args), args)


def op_online_sdo_write(project, args):
    index, subindex = sdo_address(args)
    expected = args.get('expected_raw_hex')
    if not isinstance(expected, basestring) or not re.match(r'^(?:[0-9a-fA-F]{2})+\Z', expected):
        raise ValueError('expected_raw_hex must be the bytes returned by a prior read')
    if not isinstance(args.get('expected_address'), basestring) or not args['expected_address']:
        raise ValueError('expected_address must be the configured_address returned by a prior read')
    data_type = args.get('data_type')
    data = sdo_encode(args.get('value'), data_type)
    adapter = NativeSdo(project, args)
    if adapter.address() != args['expected_address']:
        raise ValueError('Controller communication address changed; read the intended device first')
    entry = sdo_metadata(adapter, index, subindex)
    if entry:
        if not entry['writable']:
            raise ValueError('ESI marks this object read-only')
        if entry['bit_length'] != len(data) * 8 and not (data_type == 'BOOL' and entry['bit_length'] == 1):
            raise ValueError('data_type size differs from the ESI object')
        esi_type = entry['data_type']
        if esi_type in SDO_SCALARS and SDO_SCALARS[esi_type] != SDO_SCALARS[data_type]:
            raise ValueError('data_type differs from the ESI object')
    before = sdo_read_result(adapter, args)
    result = dict(adapter.identity, success=False, scope='online_device', online_verified=False,
                  write_attempted=False, write_accepted=False, readback_verified=False,
                  outcome_unknown=False, before=before, requested_raw_hex=sdo_hex(data),
                  automatic_store_command=False)
    if not before['success']:
        return dict(result, error='Pre-write read failed; no write sent')
    if before.get('decode_error') or len(before['raw_bytes']) != len(data):
        return dict(result, error='Current payload does not match data_type; no write sent')
    if before['raw_hex'] != expected.upper():
        return dict(result, error='Current bytes differ from expected_raw_hex; no write sent')
    if adapter.address() != args['expected_address']:
        return dict(result, error='Controller communication address changed; no write sent')
    result['write_attempted'] = True
    transfer = adapter.transfer(index, subindex, data)
    result['transfer'] = transfer
    result['write_attempted'] = transfer.get('transfer_started', True)
    result['write_at_utc'] = datetime.datetime.utcnow().isoformat() + 'Z'
    result['write_accepted'] = transfer['success']
    if not transfer['success']:
        result['outcome_unknown'] = result['write_attempted'] and not bool(transfer.get('native_error'))
        result['error'] = 'SDO write failed; inspect the response before any further write'
        return result
    try:
        after = sdo_read_result(adapter, args)
        result['after'] = after
        result['readback_verified'] = after['success'] and after['raw_hex'] == sdo_hex(data)
        result['success'] = result['readback_verified']
        result['online_verified'] = result['readback_verified']
        if not result['success']:
            result['error'] = 'Write accepted but readback did not confirm requested bytes'
    except Exception as exc:
        result['error'] = 'Write accepted; readback failed: ' + unicode(exc)
    return result


def op_sdo_dictionary(project, args):
    offset = _sdo_int(args, 'offset', 0, 0)
    limit = _sdo_int(args, 'limit', 50, 1, 200)
    index = _sdo_int(args, 'index', None, 1, 65535) if 'index' in args else None
    adapter = NativeSdo(project, args)
    query = unicode(args.get('query') or '').lower()
    rows = [e for e in adapter.entries if (index is None or e['index'] == index)
            and (not query or query in ('%04x:%02x %s' % (e['index'], e['subindex'], e['name'])).lower())]
    return dict(adapter.identity, success=True, scope='offline_dictionary', online_verified=False,
                items=rows[offset:offset + limit], total=len(rows), offset=offset,
                next_offset=offset + limit if offset + limit < len(rows) else None)


def op_servo_startup(project, args):
    adapter = NativeSdo(project, args)
    rows = adapter.startup()
    return dict(adapter.identity, success=True, scope='offline_project', online_verified=False, items=rows, count=len(rows))
