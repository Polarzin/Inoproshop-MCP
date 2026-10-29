# -*- coding: utf-8 -*-
"""Finite ScriptEngine batch. Executed by the vendor's normal --runscript option."""
import os, json, codecs, traceback
OWNED_IDE = False


def build_c6(project, request):
    root = request['root']
    spec = json.loads(codecs.open(os.path.join(root, 'examples/c6/interface.json'), 'r', 'utf-8').read())
    tree = op_tree(project, {})['nodes']
    device = device_object(project, 'Device')
    identity = config_fields(device.get_device_identification(), ('id', 'type', 'version'))
    if identity.get('type') != 4102 or unicode(identity.get('id')).lower() != '0000 0001':
        raise ValueError('C6 template must target the installed SoftMotion Win software controller (4102 / 0000 0001)')
    if device.get_simulation_mode():
        raise ValueError('Use the actual software-controller configuration, not IDE Simulation mode')
    pools = [n for n in tree if n['name'] == 'SoftMotion General Axis Pool']
    tasks = [n for n in tree if n['name'] == 'MainTask']
    if len(pools) != 1 or len(tasks) != 1:
        raise ValueError('Template must contain one software SoftMotion axis pool and MainTask')
    # Do not silently build on an existing demo or reuse its axes.
    if any(n['name'] in ('Feed', 'Carriage', 'Knife', 'FlyingShearDemo') for n in tree):
        raise ValueError('Use a blank controller template with no demo axes/program')
    axis_id = request.get('axis') or {'type': 1024, 'id': 'FFFF 0001', 'version': '4.0.0.0'}
    for name in ('Feed', 'Carriage', 'Knife'):
        axis = op_device_add(project, dict(axis_id, parent=pools[0]['path'], name=name))
        params = op_device_parameters(project, {'path': axis['path'], 'connector_id': '0', 'limit': 200})
        for key, value in (('fSWMaxVelocity', '100.0'), ('fSWMaxAcceleration', '200.0'), ('fSWMaxDeceleration', '200.0')):
            matches = [p for p in params['items'] if p['visible_name'] == key]
            if len(matches) != 1:
                raise ValueError('Axis parameter unavailable: ' + key)
            p = matches[0]
            op_device_parameter_write(project, {'path':axis['path'], 'connector_id':'0',
                'parameter_path':p['parameter_path'], 'expected_sha256':p['sha256'], 'value':value})
    op_create(project, {'parent':'Application', 'name':spec['program'], 'kind':'program'})
    source = {'path':'Application/' + spec['program']}
    for part in ('declaration', 'implementation'):
        source[part] = codecs.open(os.path.join(root, 'examples/c6/FlyingShearDemo.' + part + '.st'), 'r', 'utf-8').read()
    op_write(project, source)
    task = op_task(project, {'path':tasks[0]['path']})
    op_task_configure(project, {'path':tasks[0]['path'], 'expected_sha256':task['sha256'],
                              'interval_ms':10, 'priority':1, 'add_pou':spec['program']})
    require_build(project)
    configs = [n for n in op_tree(project, {})['nodes'] if n['is_symbol_config']]
    if len(configs) > 1:
        raise ValueError('Ambiguous symbol configuration')
    config_path = configs[0]['path'] if configs else op_symbols_create(project, {'path':'Application'})['path']
    symbols = op_symbols(project, {'path':config_path, 'query':spec['program'], 'limit':200})['symbols']
    for field, definition in spec['fields'].items():
        matches = [s for s in symbols if s['name'].endswith('.'+spec['program']+'.'+field) or s['name']==spec['program']+'.'+field]
        if len(matches) != 1:
            raise ValueError('Missing/ambiguous symbol: ' + field)
        item = matches[0]
        op_symbol_access(project, {'path':config_path, 'symbol':item['name'],
            'expected_configured_access':item['configured_access'], 'access':'ReadWrite' if definition.get('write') else 'Read'})
    project.save()
    verified = op_verify_symbols(project, {'expected':[{'name':'Application.'+spec['program']+'.'+name,
        'access':'ReadWrite' if definition.get('write') else 'Read', 'type':definition['iec']}
        for name, definition in spec['fields'].items()]})
    if not verified['export_verified']:
        raise ValueError('Generated symbol export verification failed')
    final_compile = op_compile(project, {})
    if final_compile['error_count']:
        raise ValueError('Final compilation failed: ' + json.dumps(final_compile))
    return {'compile':final_compile, 'symbols':verified, 'online_verified':False}


def main():
    global PROJECT_PATH, COMPILE_CATEGORY, OWNED_IDE
    with codecs.open(REQUEST_PATH, 'r', 'utf-8') as stream:
        request = json.loads(stream.read())
    with codecs.open(os.path.join(os.path.dirname(REQUEST_PATH), 'owner.json'), 'r', 'utf-8') as stream:
        owner = json.loads(stream.read())
    if owner['pid'] != os.getpid():
        raise RuntimeError('Refusing to run in an existing IDE process')
    OWNED_IDE = True
    PROJECT_PATH = request['project']
    COMPILE_CATEGORY = '97f48d64-a2a3-4856-b640-75c046e37ea9'
    # Read only this package's curated ScriptEngine helpers, not an arbitrary user script.
    api_path = os.path.join(request['root'], 'worker_api.py')
    with codecs.open(api_path, 'r', 'utf-8') as stream:
        eval(compile(stream.read(), api_path, 'exec'), globals())
    result = {'ide_pid':os.getpid(), 'ok':False, 'action':request['action'], 'project':PROJECT_PATH, 'online_verified':False, 'steps':[]}
    project = None
    try:
        system.prompt_handling = PromptHandling.LogSimplePrompts
        if request['action'] in ('create_empty', 'build_c6'):
            if os.path.exists(PROJECT_PATH):
                raise ValueError('Output exists; never overwrite or retry creation')
            parent = os.path.dirname(PROJECT_PATH)
            if not os.path.isdir(parent):
                os.makedirs(parent)
            if 'adapter' in request or 'controller' in request:
                raise ValueError('Internal controller adapters are not included')
            if request['action'] == 'build_c6' and not request.get('template'):
                raise ValueError('Provide a blank software-controller template created through the official IDE or documented ScriptEngine configuration')
            if request.get('template'):
                if request['action'] != 'build_c6':
                    raise ValueError('Only build_c6 accepts a template')
                # Exclusive file creation also protects against another process racing us.
                import System
                System.IO.File.Copy(request['template'], PROJECT_PATH, False)
                project = projects.open(PROJECT_PATH, u'', True)
                result['controller_creation'] = {'copied_template':True, 'internal_api':False}
            else:
                project = projects.create(PROJECT_PATH, True)
        else:
            project = projects.open(PROJECT_PATH, u'', True)
        if request['action'] == 'build_c6':
            result['engineering'] = build_c6(project, request)
        elif request['action'] == 'batch':
            allowed = set('tree list read read_lines patch write create rename move delete compile save device device_parameters device_parameter_write device_add repository_devices task task_configure libraries library_add symbols_create symbols symbol_access verify_symbols generate_code export_boot'.split())
            for step in request['steps']:
                if step['op'] not in allowed:
                    raise ValueError('Unsupported offline operation: ' + step['op'])
                value = globals()['op_' + step['op']](project, step.get('args') or {})
                result['steps'].append({'op':step['op'], 'result':value})
                if isinstance(value, dict) and value.get('error_count', 0):
                    raise ValueError('Compiler errors; inspect diagnostics')
        project.save()
        result['ok'] = True
    except Exception as exc:
        result['error'] = unicode(repr(exc))
        result['trace'] = unicode(traceback.format_exc())
        # Preserve partial offline edits for diagnosis; no automatic rebuild/retry.
        if project is not None:
            try:
                project.save()
            except Exception:
                pass
    finally:
        try:
            if project is not None:
                project.close()
        except Exception as exc:
            result['ok'] = False
            result['close_error'] = unicode(repr(exc))
        with codecs.open(os.path.join(os.path.dirname(REQUEST_PATH), 'result.json'), 'w', 'utf-8') as stream:
            stream.write(unicode(json.dumps(result, ensure_ascii=True)))


try:
    main()
finally:
    if OWNED_IDE:
        system.exit()
