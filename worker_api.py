# -*- coding: utf-8 -*-
import os, re, json, codecs, hashlib
try:
    basestring
except NameError:
    basestring = str
    long = int
    unicode = str

def obj_name(o):
    try:
        return o.get_name()
    except Exception:
        try:
            return o.get_name(False)
        except Exception:
            return None

def has_attr_true(o, attr):
    try:
        return bool(getattr(o, attr))
    except Exception:
        return False

def find_app(project):
    try:
        app = project.active_application
        if app:
            return app
    except Exception:
        pass
    try:
        hits = list(project.find("Application", True))
        if hits:
            return hits[0]
    except Exception:
        pass
    return None

def walk_pous(node, prefix, out, want_textual):
    try:
        children = list(node.get_children(False))
    except Exception:
        children = []
    for child in children:
        nm = obj_name(child)
        if nm is None:
            continue
        path = (prefix + "/" + nm) if prefix else nm
        has_impl = has_attr_true(child, "has_textual_implementation")
        has_decl = has_attr_true(child, "has_textual_declaration")
        if (not want_textual) or has_impl or has_decl:
            out.append({"path": path, "name": nm, "has_impl": has_impl, "has_decl": has_decl})
        walk_pous(child, path, out, want_textual)

def find_exact_path(project, path):
    """New tools use explicit slash paths; never fall back to a same-name descendant."""
    if not isinstance(path, basestring):
        raise ValueError("An explicit object path is required")
    parts = path.replace("\\", "/").strip("/").split("/")
    if not parts or any(not p for p in parts):
        raise ValueError("An explicit object path is required")
    current = project
    app = find_app(project)
    root_matches = [c for c in project.get_children(False) if obj_name(c) == parts[0]]
    if not root_matches and app is not None and parts[0] == obj_name(app):
        if len(list(project.find(parts[0], True))) != 1:
            raise ValueError("Application alias is ambiguous; use the full tree path")
        current, parts = app, parts[1:]
    for part in parts:
        matches = [c for c in current.get_children(False) if obj_name(c) == part]
        if len(matches) != 1:
            raise ValueError("Object path missing or ambiguous: %s" % path)
        current = matches[0]
    return current

def integer_arg(args, name, default, minimum, maximum=None):
    value = args.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, long)):
        raise ValueError("%s must be an integer" % name)
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError("%s out of range" % name)
    return value

def text_document(project, args):
    obj = find_exact_path(project, args["path"])
    section = args.get("section", "implementation")
    if section not in ("declaration", "implementation"):
        raise ValueError("section must be declaration or implementation")
    if not has_attr_true(obj, "has_textual_" + section):
        raise ValueError("Object has no textual %s" % section)
    return getattr(obj, "textual_" + section)

def text_sha256(text):
    return hashlib.sha256(unicode(text).encode("utf-8")).hexdigest()

def op_read_lines(project, args):
    doc = text_document(project, args)
    start = integer_arg(args, "start_line", 1, 1)
    count = integer_arg(args, "line_count", 80, 1, 500)
    total = doc.linecount
    if start > max(1, total):
        raise ValueError("start_line exceeds document line count")
    text = unicode(doc.text)
    lines = [unicode(doc.get_line(i)) for i in range(start - 1, min(total, start - 1 + count))]
    newline = u"\r\n" if u"\r\n" in text else u"\n"
    return {"path": args["path"], "section": args.get("section", "implementation"),
            "start_line": start, "total_lines": total, "line_count": len(lines),
            "text": newline.join(lines), "sha256": text_sha256(text),
            "next_line": start + len(lines) if start - 1 + len(lines) < total else None}

def op_patch(project, args):
    doc = text_document(project, args)
    before = unicode(doc.text)
    if args.get("expected_sha256") != text_sha256(before):
        raise ValueError("POU revision conflict; read current text before patching")
    old, new = args.get("old_text"), args.get("new_text")
    if not isinstance(old, basestring) or not old or not isinstance(new, basestring):
        raise ValueError("old_text must be nonempty and new_text must be text")
    newline = u"\r\n" if u"\r\n" in before else u"\n"
    normalized = new.replace(u"\r\n", u"\n").replace(u"\r", u"\n").replace(u"\n", newline)
    newline_normalized = normalized != new
    new = normalized
    index = before.find(old)
    if index < 0 or before.find(old, index + 1) >= 0:
        raise ValueError("old_text must match exactly once")
    expected = before[:index] + new + before[index + len(old):]
    changed = before != expected
    if changed:
        # ScriptTextDocument offsets are .NET UTF-16 code units (also for non-BMP text).
        offset = len(before[:index].encode("utf-16-le")) // 2
        length = len(old.encode("utf-16-le")) // 2
        doc.replace(offset, length, new)
        if unicode(doc.text) != expected:
            raise RuntimeError("Patch executed but readback differs; inspect current text before retrying")
    saved = False
    if args.get("save", False) and changed:
        project.save()
        saved = True
    return {"path": args["path"], "section": args.get("section", "implementation"),
            "changed": changed, "saved": saved, "newline_normalized": newline_normalized,
            "sha256": text_sha256(doc.text)}

def config_fields(obj, names):
    """Read offline properties only; preserve null/bool and report unavailable fields."""
    result, errors = {}, {}
    for name in names:
        try:
            value = getattr(obj, name)
            result[name] = value if value is None or isinstance(value, (bool, int, long, float)) else unicode(value)
        except Exception as exc:
            errors[name] = unicode(exc)
    if errors:
        result["errors"] = errors
    return result

def device_object(project, path):
    obj = find_exact_path(project, path)
    if not has_attr_true(obj, "is_device"):
        raise ValueError("Object is not a device: %s" % path)
    return obj

def device_parameter_children(obj, args):
    connector_id = args.get("connector_id")
    parameters = obj.device_parameters
    if connector_id is not None:
        connectors = [c for c in obj.connectors if unicode(c.connector_id) == unicode(connector_id)]
        if len(connectors) != 1:
            raise ValueError("Connector missing or ambiguous")
        parameters = connectors[0].host_parameters
    parent_path = args.get("parameter_path", [])
    if not isinstance(parent_path, list):
        raise ValueError("parameter_path must be an array of zero-based indices")
    children, ancestors = list(parameters), []
    for index in parent_path:
        integer_arg({"index": index}, "index", 0, 0)
        if index >= len(children):
            raise ValueError("parameter_path index out of range")
        parent = children[index]
        ancestors.append(unicode(parent.identifier))
        children = list(parent)
    return children, ancestors

def device_parameter_record(obj, args, p, indices, ancestors):
    entry = config_fields(p, ("identifier", "visible_name", "value", "has_sub_elements", "is_mappable_io"))
    entry["parameter_path"] = indices
    if entry.get("is_mappable_io") is True:
        try:
            entry["io_mapping"] = config_fields(p.io_mapping, ("variable", "manual_iec_address", "automatic_iec_address"))
        except Exception as exc:
            entry.setdefault("errors", {})["io_mapping"] = unicode(exc)
    # 绑定设备身份、父参数链和当前值，索引漂移或人工改动后必须重新读取。
    try:
        identity = {"guid": unicode(obj.guid), "device": config_fields(obj.get_device_identification(), ("id", "type", "version")),
                    "path": args["path"], "connector_id": args.get("connector_id"), "ancestors": ancestors}
        if entry.get("errors") or entry.get("io_mapping", {}).get("errors") or identity["device"].get("errors"):
            raise ValueError("Parameter snapshot contains unreadable fields")
        entry["identity_sha256"] = text_sha256(json.dumps([identity, entry["identifier"], indices], sort_keys=True, ensure_ascii=True))
        entry["sha256"] = text_sha256(json.dumps([identity, entry], sort_keys=True, ensure_ascii=True))
    except Exception as exc:
        entry["write_unavailable"] = unicode(exc)
    return entry

def op_device(project, args):
    obj = device_object(project, args["path"])
    simulation = obj.get_simulation_mode() if hasattr(obj, "get_simulation_mode") else None
    return {"path": args["path"], "simulation_mode": simulation,
            "identification": config_fields(obj.get_device_identification(), ("id", "type", "version")),
            "connectors": [config_fields(c, ("connector_id", "interface", "interface_name", "module_type")) for c in obj.connectors]}

def op_device_parameters(project, args):
    obj = device_object(project, args["path"])
    children, ancestors = device_parameter_children(obj, args)
    parent_path = args.get("parameter_path", [])
    offset = integer_arg(args, "offset", 0, 0)
    limit = integer_arg(args, "limit", 50, 1, 200)
    items = [device_parameter_record(obj, args, children[i], parent_path + [i], ancestors)
             for i in range(offset, min(len(children), offset + limit))]
    return {"path": args["path"], "connector_id": args.get("connector_id"), "parameter_path": parent_path,
            "offset": offset, "total": len(children), "items": items,
            "next_offset": offset + len(items) if offset + len(items) < len(children) else None}

def write_device_field(project, args, mapping=False):
    obj = device_object(project, args["path"])
    indices = args.get("parameter_path")
    if not isinstance(indices, list) or not indices:
        raise ValueError("parameter_path must identify one parameter")
    children, ancestors = device_parameter_children(obj, dict(args, parameter_path=indices[:-1]))
    index = integer_arg({"index": indices[-1]}, "index", 0, 0)
    if index >= len(children):
        raise ValueError("parameter_path index out of range")
    p = children[index]
    before = device_parameter_record(obj, args, p, indices, ancestors)
    if not before.get("sha256") or before["sha256"] != args.get("expected_sha256"):
        raise ValueError("Device parameter revision conflict or unreadable snapshot; re-read before writing")
    if mapping:
        if not p.is_mappable_io:
            raise ValueError("Parameter is not mappable IO")
        target, field, desired = p.io_mapping, "variable", args["variable"]
        if desired is not None and not isinstance(desired, basestring):
            raise ValueError("variable must be a string or null to clear mapping")
        old = before["io_mapping"]["variable"]
    else:
        if p.has_sub_elements:
            raise ValueError("Write an individual leaf parameter, not a compound value")
        target, field, desired = p, "value", args["value"]
        if not isinstance(desired, basestring):
            raise ValueError("value must use the native string representation")
        old = before["value"]
    changed = old != desired
    if changed:
        setattr(target, field, desired)
    # setter 可能重建底层对象，重新定位并读取，不使用写前快照作为证明。
    fresh = device_object(project, args["path"])
    children, ancestors = device_parameter_children(fresh, dict(args, parameter_path=indices[:-1]))
    after = device_parameter_record(fresh, args, children[index], indices, ancestors)
    if after.get("identity_sha256") != before["identity_sha256"]:
        raise RuntimeError("Setting executed but readback target identity changed; inspect configuration before retrying")
    observed = after.get("io_mapping", {}).get("variable") if mapping else after.get("value")
    if after.get("write_unavailable") or observed != desired:
        raise RuntimeError("Setting executed but readback differs; inspect current configuration before retrying: %s" % json.dumps(after, ensure_ascii=True))
    saved = False
    if changed and args.get("save", False):
        project.save()
        saved = True
    return {"path": args["path"], "before": before, "after": after, "changed": changed,
            "saved": saved, "scope": "offline_project", "online_verified": False}

def op_device_parameter_write(project, args):
    return write_device_field(project, args)

def walk_tree(node, prefix, out, depth):
    """从工程根递归遍历完整设备树(含硬件节点), 产出预序展开列表.

    功能:
        与 walk_pous 同形, 但不做 textual 过滤, 并带 depth/has_children, 供上位机
        web「设备」标签按 InoProShop 设备树原序逐级渲染(硬件节点只展开, 程序节点可点开编辑)
    参数:
        node: 当前对象(首层传 project 根); prefix: 已累积的斜杠路径; out: 结果列表(就地追加);
        depth: 当前层级深度(根的直接子级为 0)
    返回:
        无(结果就地写入 out)
    """
    try:
        children = list(node.get_children(False))
    except Exception:
        children = []
    for child in children:
        nm = obj_name(child)
        if nm is None:
            continue
        path = (prefix + "/" + nm) if prefix else nm
        # 探测是否可展开(有无子级), 兄弟顺序即 get_children 的 InoProShop 树序
        try:
            kids = list(child.get_children(False))
        except Exception:
            kids = []
        out.append({"path": path, "name": nm, "depth": depth,
                    "is_device": has_attr_true(child, "is_device"),
                    "is_symbol_config": has_attr_true(child, "is_symbol_config"),
                    "has_impl": has_attr_true(child, "has_textual_implementation"),
                    "has_decl": has_attr_true(child, "has_textual_declaration"),
                    "has_children": len(kids) > 0})
        walk_tree(child, path, out, depth + 1)


# ---------- 操作 ----------

def op_tree(project, args):
    out = []
    walk_tree(project, "", out, 0)  # 从工程根走, 不做 textual 过滤 -> 含硬件节点
    return {"nodes": out, "count": len(out)}

def op_list(project, args):
    want_textual = args.get("textual_only", True)
    app = find_app(project)
    root = app if app else project
    prefix = obj_name(app) if app else ""
    out = []
    walk_pous(root, prefix, out, want_textual)
    return {"pous": out, "count": len(out)}

def op_read(project, args):
    return object_record(find_exact_path(project, args["path"]))

def op_write(project, args):
    obj = find_exact_path(project, args["path"])
    expected = {}
    # Validate both sections before the first edit. Property Get/Set are child paths.
    for section in ("declaration", "implementation"):
        if section not in args:
            continue
        value = args[section]
        if not isinstance(value, basestring):
            raise ValueError("%s must be text" % section)
        if not has_attr_true(obj, "has_textual_" + section):
            raise ValueError("Object has no textual %s; use the Get/Set child path for a property" % section)
        doc = getattr(obj, "textual_" + section)
        newline = u"\r\n" if u"\r\n" in unicode(doc.text) else u"\n"
        expected[section] = value.replace(u"\r\n", u"\n").replace(u"\r", u"\n").replace(u"\n", newline)
    if not expected:
        raise ValueError("Provide declaration and/or implementation")
    for section, value in expected.items():
        getattr(obj, "textual_" + section).replace(value)
    after = op_read(project, args)
    if any(after[section] != value for section, value in expected.items()):
        raise RuntimeError("Write executed but readback differs; inspect current text before retrying")
    saved = bool(args.get("save", False))
    if saved:
        project.save()
    after.update(updated=sorted(expected), saved=saved)
    return after

def _create_child(parent, kind, name, language, args=None):
    """使用原生签名，只创建 ST；不以捕获 TypeError 重试有副作用的创建。"""
    if language not in (None, "ST"):
        raise ValueError("Only ST is supported")
    if kind == "action":
        return parent.create_action(name)
    args = args or {}
    if kind in ("pou", "program", "function"):
        # 本机 CHM: create_pou(name, type=FunctionBlock, language=None, ...)
        if kind == "function":
            return parent.create_pou(name, type=PouType.Function, return_type=args.get("return_type", "INT"))
        return parent.create_pou(name, type=PouType.Program if kind == "program" else PouType.FunctionBlock)
    if kind == "method":
        return parent.create_method(name, return_type=args.get("return_type"))
    if kind == "property":
        return parent.create_property(name, return_type=args.get("return_type", "INT"))
    if kind == "dut":
        types = {"structure": DutType.Structure, "enumeration": DutType.Enumeration,
                 "alias": DutType.Alias, "union": DutType.Union}
        return parent.create_dut(name, type=types[args.get("dut_type", "structure")], baseType=args.get("base_type"))
    if kind == "folder":
        return parent.create_folder(name)
    if kind == "gvl":
        return parent.create_gvl(name)
    if kind == "task":
        return parent.create_task(name)
    raise ValueError("Unsupported object kind")

def direct_child(parent, name):
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError("name must be an IEC identifier")
    matches = [c for c in parent.get_children(False) if obj_name(c) == name]
    if len(matches) > 1:
        raise ValueError("Ambiguous child name")
    return matches[0] if matches else None

def op_repository_devices(project, args):
    offset = integer_arg(args, "offset", 0, 0)
    limit = integer_arg(args, "limit", 50, 1, 200)
    query = unicode(args.get("query") or "").lower()
    rows = []
    for item in device_repository.get_all_devices():
        ident = config_fields(item.device_id, ("id", "type", "version"))
        if args.get("type") is not None and ident["type"] != args["type"]:
            continue
        info = config_fields(item.device_info, ("name", "vendor"))
        if query and query not in (unicode(info) + unicode(ident)).lower():
            continue
        rows.append(dict(identification=ident, info=info))
    rows.sort(key=lambda r: (unicode(r["identification"]["type"]), r["identification"]["id"], r["identification"]["version"]))
    return {"items": rows[offset:offset + limit], "total": len(rows),
            "next_offset": offset + limit if offset + limit < len(rows) else None,
            "scope": "installed_repository"}

def op_device_add(project, args):
    parent_path, name = args.get("parent") or "", args["name"]
    parent = find_exact_path(project, parent_path) if parent_path else project
    existing = direct_child(parent, name)
    if existing is not None:
        raise ValueError("Object already exists; inspect its identity before reuse")
    ident = DeviceID(args["type"], args["id"], args["version"])
    # 原生 add 返回 void，按精确父路径重新取对象；兼容性由原生连接器校验。
    if not parent_path:
        raise ValueError("Top-level devices require the InoProShop wizard; create a blank ST controller with the normal IDE wizard")
    parent.add(name, ident)
    full = parent_path.rstrip("/") + "/" + name if parent_path else name
    result = op_device(project, {"path": full})
    if result["identification"] != {k: args[k] for k in ("type", "id", "version")}:
        raise ValueError("Device created but identity readback differs; inspect tree before retry")
    if args.get("save", False):
        project.save()
    result.update(created=True, saved=args.get("save", False), scope="offline_project", online_verified=False)
    return result

def op_task(project, args):
    task = find_exact_path(project, args["path"])
    if not has_attr_true(task, "is_task"):
        raise ValueError("Object is not a task")
    result = config_fields(task, ("kind_of_task", "interval", "interval_unit", "priority"))
    result.update(path=args["path"], pous=list(task.pous))
    result["sha256"] = text_sha256(json.dumps(result, sort_keys=True))
    return result

def op_task_configure(project, args):
    before = op_task(project, args)
    if before["sha256"] != args["expected_sha256"]:
        raise ValueError("Task revision conflict; read again")
    interval = integer_arg(args, "interval_ms", 10, 1, 10000)
    priority = integer_arg(args, "priority", 1, 0, 31)
    pou = args.get("add_pou")
    if pou and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", pou):
        raise ValueError("add_pou must be a simple program name")
    task = find_exact_path(project, args["path"])
    task.kind_of_task = KindOfTask.Cyclic
    task.interval = unicode(interval)
    task.interval_unit = "ms"
    task.priority = unicode(priority)
    # 本机原生集合枚举程序名；只追加所需调用，不清空已有调用。
    if pou and pou not in before["pous"]:
        task.pous.add(pou, "Synthetic MCP example")
    result = op_task(project, args)
    if args.get("save", False):
        project.save()
    result.update(saved=args.get("save", False), scope="offline_project", online_verified=False)
    return result

def app_libman(project, path):
    parent = find_exact_path(project, path) if path else project
    managers = [c for c in parent.get_children(False) if has_attr_true(c, "is_libman")]
    if len(managers) != 1:
        raise ValueError("Expected one existing library manager under the exact parent")
    return managers[0]

def op_libraries(project, args):
    manager = app_libman(project, args["path"])
    rows = []
    for ref in manager.references:
        row = config_fields(ref, ("name", "is_placeholder", "is_managed", "namespace", "qualified_only"))
        if row.get("is_placeholder"):
            row.update(config_fields(ref, ("effective_resolution", "default_resolution")))
        rows.append(row)
    return {"path": args["path"], "references": rows, "scope": "offline_project"}

def op_library_add(project, args):
    manager = app_libman(project, args["path"])
    name = args["display_name"]
    # 必须为明确版本的已安装库，不能默认漂移到最新版本。
    if not re.match(r"^.+, [0-9]+(?:\.[0-9]+){1,3} \(.+\)$", name):
        raise ValueError("Use exact installed library display name: Name, Version (Company)")
    installed = librarymanager.find_library(name)
    if not installed or installed[0] is None:
        raise ValueError("Exact library is not installed")
    def matches(row):
        return row.get("name") == name or row.get("effective_resolution") == name
    # 原生向导使用占位符引用；已解析到相同身份时保留原有引用，不再添加重复库。
    added = not any(matches(r) for r in op_libraries(project, args)["references"])
    if added:
        manager.add_library(name)
    result = op_libraries(project, args)
    if not any(matches(r) for r in result["references"]):
        raise ValueError("Library add did not read back; inspect before retry")
    if args.get("save", False):
        project.save()
    result.update(added=added, saved=args.get("save", False))
    return result

def op_symbols_create(project, args):
    app = find_exact_path(project, args["path"])
    if any(has_attr_true(c, "is_symbol_config") for c in app.get_children(False)):
        raise ValueError("Symbol Configuration already exists; inspect before reuse")
    from System import Guid
    obj = app.create_symbol_config(False, True, Guid.Empty)
    if not has_attr_true(obj, "is_symbol_config"):
        raise ValueError("Native factory did not return a symbol configuration")
    if args.get("save", False):
        project.save()
    return {"path": args["path"].rstrip("/") + "/" + obj_name(obj), "created": True,
            "saved": args.get("save", False), "online_verified": False}

def op_create(project, args):
    """Create one ST object under an exact parent (empty parent means project root).

    kind: action (default), pou (FB), program, function, method, property, dut,
    folder, gvl, task. return_type applies to function/method/property;
    dut_type is structure/enumeration/alias/union; base_type is the DUT base.
    Property Get/Set are reported as children and edited with read/write/patch.
    """
    parent_path = args["parent"]
    name = args["name"]
    kind = args.get("kind") or "action"
    if kind not in ("action", "pou", "program", "function", "method", "property", "dut", "folder", "gvl", "task"):
        raise ValueError("Unsupported object kind")
    if args.get("language") not in (None, "ST"):
        raise ValueError("Only ST is supported")
    validate_object_name(name, kind == "folder")
    for field in ("return_type", "base_type"):
        if field in args and (not isinstance(args[field], basestring) or not args[field].strip()):
            raise ValueError("%s must be nonempty text when provided" % field)
    if "return_type" in args and kind not in ("function", "method", "property"):
        raise ValueError("return_type applies only to function/method/property")
    if ("dut_type" in args or "base_type" in args) and kind != "dut":
        raise ValueError("dut_type/base_type apply only to dut")
    if kind == "dut" and args.get("dut_type", "structure") not in ("structure", "enumeration", "alias", "union"):
        raise ValueError("dut_type must be structure, enumeration, alias or union")
    parent = object_parent(project, parent_path)
    require_free_name(parent, name)
    # Some native factories return void; read the child from its exact parent.
    _create_child(parent, kind, name, args.get("language"), args)
    full = child_path(parent, name)
    after = op_read(project, {"path": full})
    after.update(created=True, saved=save_if_requested(project, args))
    return after


def object_path(obj):
    parts = []
    while not obj.is_root:
        parts.append(obj_name(obj))
        obj = obj.parent
    return "/".join(reversed(parts))


def object_parent(project, path):
    if not isinstance(path, basestring):
        raise ValueError("parent must be a path string (empty for project root)")
    return find_exact_path(project, path) if path else project


def child_path(parent, name):
    prefix = object_path(parent)
    return prefix + "/" + name if prefix else name


def object_record(obj):
    """Finite offline snapshot; never evaluates caller-supplied attributes/code."""
    result = {"path": object_path(obj), "name": obj_name(obj), "guid": unicode(obj.guid),
              "is_folder": has_attr_true(obj, "is_folder"),
              "children": [{"path": child_path(obj, obj_name(c)), "name": obj_name(c),
                            "guid": unicode(c.guid)} for c in obj.get_children(False)]}
    for section, flag in (("declaration", "has_decl"), ("implementation", "has_impl")):
        result[flag] = has_attr_true(obj, "has_textual_" + section)
        result[section] = unicode(getattr(obj, "textual_" + section).text) if result[flag] else u""
    return result


def validate_object_name(name, folder=False):
    if not isinstance(name, basestring) or not name or name != name.strip():
        raise ValueError("name must be nonempty text without surrounding whitespace")
    if folder:
        if name in (".", "..") or any(c in name for c in ("/", "\\")) or any(ord(c) < 32 for c in name):
            raise ValueError("Folder name must be one path segment")
    elif not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError("name must be an IEC identifier")


def require_free_name(parent, name, exclude=None):
    # IEC identifiers are case insensitive even when the displayed path is not.
    if any(obj_name(c).lower() == name.lower() and unicode(c.guid) != exclude
           for c in parent.get_children(False)):
        raise ValueError("Target name already exists (case insensitive)")


def save_if_requested(project, args):
    saved = bool(args.get("save", False))
    if saved:
        project.save()
    return saved


def op_rename(project, args):
    obj = find_exact_path(project, args["path"])
    name = args["name"]
    validate_object_name(name, has_attr_true(obj, "is_folder"))
    parent, guid, old_path = obj.parent, unicode(obj.guid), object_path(obj)
    require_free_name(parent, name, guid)
    changed = obj_name(obj) != name
    if changed:
        obj.rename(name)
    after = op_read(project, {"path": child_path(parent, name)})
    if after["guid"] != guid:
        raise RuntimeError("Rename executed but identity readback differs; inspect before retry")
    after.update(old_path=old_path, changed=changed, saved=save_if_requested(project, args))
    return after


def op_move(project, args):
    obj = find_exact_path(project, args["path"])
    parent = object_parent(project, args["parent"])
    guid, old_path, old_parent = unicode(obj.guid), object_path(obj), obj.parent
    ancestor = parent
    while not ancestor.is_root:
        if unicode(ancestor.guid) == guid:
            raise ValueError("Cannot move an object into itself or its descendant")
        ancestor = ancestor.parent
    require_free_name(parent, obj_name(obj), guid)
    changed = object_path(old_parent) != object_path(parent)
    name = obj_name(obj)
    if changed:
        obj.move(parent)
    after = op_read(project, {"path": child_path(parent, name)})
    if after["guid"] != guid or (changed and any(unicode(c.guid) == guid for c in old_parent.get_children(False))):
        raise RuntimeError("Move executed but location/identity readback differs; inspect before retry")
    after.update(old_path=old_path, changed=changed, saved=save_if_requested(project, args))
    return after


def op_delete(project, args):
    """Delete exactly this object; descendants require recursive=true.

    Read/tree first to inspect scope. The receipt lists every removed path/GUID.
    No recursive name lookup, no repeated remove after an unknown result.
    """
    recursive = args.get("recursive", False)
    if not isinstance(recursive, bool):
        raise ValueError("recursive must be boolean")
    obj = find_exact_path(project, args["path"])
    parent, guid, path = obj.parent, unicode(obj.guid), object_path(obj)
    children = list(obj.get_children(False))
    if children and not recursive:
        raise ValueError("Object has children; read/tree its scope and set recursive=true to delete the subtree")
    removed = []
    def collect(node):
        removed.append({"path": object_path(node), "guid": unicode(node.guid)})
        for child in node.get_children(False):
            collect(child)
    collect(obj)
    obj.remove()
    if any(unicode(c.guid) == guid or obj_name(c) == removed[0]["path"].split("/")[-1]
           for c in parent.get_children(False)):
        raise RuntimeError("Delete executed but object is still present; inspect before retry")
    return {"path": path, "deleted": True, "recursive": recursive, "removed": removed,
            "removed_count": len(removed), "saved": save_if_requested(project, args)}

def _collect_compile_messages():
    """Collect the current compiler-category messages without starting a build."""
    errors = []
    warnings = []
    info_count = 0
    try:
        msgs = list(system.get_message_objects(COMPILE_CATEGORY))
    except Exception:
        msgs = []
    for m in msgs:
        try:
            sev = unicode(getattr(m, "severity", u""))
        except Exception:
            sev = u""
        try:
            txt = unicode(getattr(m, "text", u""))
        except Exception:
            txt = u""
        rec = {"severity": sev, "text": txt}
        low = sev.lower()
        if "error" in low:
            errors.append(rec)
        elif "warning" in low:
            warnings.append(rec)
        else:
            info_count += 1
    return {"error_count": len(errors), "warning_count": len(warnings), "info_count": info_count,
            "errors": errors, "warnings": warnings}

def op_compile(project, args):
    app = find_app(project)
    if app is None:
        raise RuntimeError("工程内未找到可编译的 Application")
    try:
        system.clear_messages(COMPILE_CATEGORY)
    except Exception:
        pass
    app.build()
    return _collect_compile_messages()

def _symbol_xml_paths(app):
    """Return Symbol Configuration XML candidates for the active application.

    CODESYS names the generated file as
    ``<project>.<device>.<application>.xml``.  Prefer that exact name, but retain
    a header-checked directory scan for vendor profiles whose device hierarchy
    cannot be inspected through ScriptEngine.
    """
    project_path = os.path.abspath(PROJECT_PATH)
    project_dir = os.path.dirname(project_path)
    project_name = os.path.splitext(os.path.basename(project_path))[0]
    app_name = obj_name(app) or "Application"

    # The application normally sits below "PLC Logic" below the controller.
    # Keep the uppermost ScriptDeviceObject name so nested logical-device nodes
    # do not replace the physical device name used by CODESYS in the filename.
    device_name = None
    current = app
    for _ in range(32):
        if current is None:
            break
        if has_attr_true(current, "is_device"):
            nm = obj_name(current)
            if nm:
                device_name = nm
        try:
            parent = current.parent
        except Exception:
            break
        if parent is current:
            break
        current = parent

    paths = []
    if device_name:
        paths.append(os.path.join(
            project_dir, "%s.%s.%s.xml" % (project_name, device_name, app_name)))

    try:
        names = os.listdir(project_dir)
    except Exception:
        names = []
    prefix = project_name + "."
    suffix = "." + app_name + ".xml"
    for name in names:
        if not name.startswith(prefix) or not name.endswith(suffix):
            continue
        path = os.path.join(project_dir, name)
        if path not in paths:
            paths.append(path)
    return paths

def _is_symbol_configuration_xml(path):
    try:
        f = open(path, "rb")
        try:
            head = f.read(4096)
        finally:
            f.close()
        return b"<Symbolconfiguration" in head
    except Exception:
        return False

def op_generate_code(project, args):
    """Generate the active application's Symbol Configuration XML offline.

    This operation intentionally calls only ``app.generate_code()``.  It never
    creates an online application and never calls login/download/deploy APIs.
    """
    app = find_app(project)
    if app is None:
        raise RuntimeError("工程内未找到可生成代码的 Application")

    before = {}
    for path in _symbol_xml_paths(app):
        try:
            st = os.stat(path)
            before[os.path.abspath(path)] = (st.st_mtime, st.st_size)
        except Exception:
            pass

    try:
        system.clear_messages(COMPILE_CATEGORY)
    except Exception:
        pass
    app.generate_code()
    messages = _collect_compile_messages()

    candidates = [os.path.abspath(p) for p in _symbol_xml_paths(app)
                  if _is_symbol_configuration_xml(p)]
    if not candidates:
        raise RuntimeError(
            "生成代码完成，但项目目录未找到 Symbolconfiguration XML；请确认工程包含 Symbols 对象")
    xml_path = max(candidates, key=lambda p: os.path.getmtime(p))
    stat = os.stat(xml_path)
    previous = before.get(xml_path)
    result = dict(messages)
    result.update({
        "generated": messages["error_count"] == 0,
        "application": obj_name(app),
        "xml_path": xml_path,
        "xml_mtime": stat.st_mtime,
        "xml_size": stat.st_size,
        "xml_changed": previous is None or previous != (stat.st_mtime, stat.st_size),
    })
    return result

def op_save(project, args):
    project.save()
    return {"saved": True}


# ---------- Symbol configuration (offline IDE model, never PLC login) ----------

def symbol_config(project, args):
    cfg = find_exact_path(project, args["path"])
    if not has_attr_true(cfg, "is_symbol_config"):
        raise ValueError("Path is not a Symbol Configuration object")
    app = find_app(project)
    if app is None or not any(unicode(o.guid) == unicode(cfg.guid) for o in app.get_children(True)):
        raise ValueError("Symbol Configuration must belong to the active Application used for build/export")
    return cfg

def symbol_variables(cfg):
    for signature in cfg.get_all_signatures(False):
        for variable in signature.variables:
            yield unicode(signature.full_qualified_name) + u"." + unicode(variable.name), variable

def symbol_record(name, variable):
    record = config_fields(variable, ("type", "configured_access", "attribute_access", "effective_access", "maximal_access"))
    record["name"] = name
    return record

def require_build(project):
    result = op_compile(project, {})
    if result["error_count"]:
        raise RuntimeError("Build failed; symbol model is not current: %s" % json.dumps(result, ensure_ascii=True))

def op_symbols(project, args):
    cfg = symbol_config(project, args)
    require_build(project)
    query = args.get("query", u"").lower()
    offset = integer_arg(args, "offset", 0, 0)
    limit = integer_arg(args, "limit", 50, 1, 200)
    matches = [(name, var) for name, var in symbol_variables(cfg) if query in name.lower()]
    return {"path": args["path"], "total": len(matches), "offset": offset,
            "symbols": [symbol_record(name, var) for name, var in matches[offset:offset + limit]],
            "next_offset": offset + limit if offset + limit < len(matches) else None,
            "scope": "built_project", "application": obj_name(find_app(project)), "online_verified": False}

def op_symbol_access(project, args):
    import System
    cfg = symbol_config(project, args)
    require_build(project)
    matches = [(name, var) for name, var in symbol_variables(cfg) if name == args["symbol"]]
    if len(matches) != 1:
        raise ValueError("Symbol missing or ambiguous; use exact name from symbols query")
    name, var = matches[0]
    before = symbol_record(name, var)
    if before["configured_access"] != args["expected_configured_access"]:
        raise ValueError("Symbol access conflict; re-read configuration")
    desired = args["access"]
    if desired not in ("None", "Read", "Write", "ReadWrite"):
        raise ValueError("Unsupported access")
    if before["attribute_access"] not in ("Void", desired):
        raise ValueError("Declaration attribute controls access; patch its symbol pragma first")
    value = System.Enum.Parse(var.configured_access.GetType(), desired)
    if int(value) & ~int(var.maximal_access):
        raise ValueError("Requested access exceeds the symbol maximal_access")
    changed = before["configured_access"] != desired
    if changed:
        var.configured_access = value
    # Mutation can invalidate the compiler wrapper; obtain a fresh handle.
    after = next(symbol_record(n, v) for n, v in symbol_variables(cfg) if n == name)
    if after["configured_access"] != desired or after["effective_access"] != desired:
        raise RuntimeError("Symbol setting executed but effective readback differs; re-read before retrying")
    saved = False
    if changed and args.get("save", False):
        project.save()
        saved = True
    return {"before": before, "after": after, "changed": changed, "saved": saved,
            "application": obj_name(find_app(project)), "online_verified": False}

def verify_symbol_xml(xml_path, expected):
    import xml.etree.ElementTree as ET
    with codecs.open(xml_path, "r", "utf-8-sig") as source:
        root = ET.fromstring(source.read())
    local = lambda tag: tag.rsplit("}", 1)[-1]
    if local(root.tag) != "Symbolconfiguration":
        raise ValueError("Not a Symbolconfiguration XML")
    types = {}
    for elem in (root.iter() if hasattr(root, "iter") else root.getiterator()):
        if local(elem.tag).startswith("Type") and elem.get("name"):
            types[elem.get("name")] = elem.get("iecname")
    nodes = {}
    def walk(elem, prefix):
        for child in elem:
            if local(child.tag) != "Node":
                continue
            name = prefix + [child.get("name", "")]
            nodes.setdefault(u".".join(name), []).append(child)
            walk(child, name)
    for elem in root:
        if local(elem.tag) == "NodeList":
            walk(elem, [])
    checks = []
    for spec in expected:
        hits = nodes.get(spec["name"], [])
        check = {"name": spec["name"], "expected_access": spec["access"], "found": len(hits) == 1}
        if len(hits) == 1:
            node = hits[0]
            check["access"] = node.get("access")
            check["type"] = types.get(node.get("type")) or node.get("type")
            check["passed"] = check["access"] == spec["access"] and (not spec.get("type") or check["type"] == spec["type"])
        else:
            check["passed"] = False
        checks.append(check)
    return {"checks": checks, "export_verified": all(c["passed"] for c in checks), "online_verified": False}

def op_verify_symbols(project, args):
    expected = args.get("expected")
    if not isinstance(expected, list) or not expected or len(expected) > 100:
        raise ValueError("expected must contain 1..100 symbol specifications")
    generated = op_generate_code(project, {})
    if not generated["generated"] or not generated["xml_changed"]:
        return {"export_verified": False, "online_verified": False, "generation": generated,
                "reason": "Generation failed or XML was not refreshed; no fresh export proof"}
    result = verify_symbol_xml(generated["xml_path"], expected)
    result["generation"] = generated
    return result


# ---------- C1 IDE Simulation：不接通信路径或物理 IP ----------



def op_export_boot(project, args):
    """Export a new native boot package offline; never creates an online session."""
    import tempfile
    device = device_object(project, 'Device')
    identity = config_fields(device.get_device_identification(), ('id', 'type', 'version'))
    if identity.get('type') != 4102 or unicode(identity.get('id')).lower() != '0000 0001' or device.get_simulation_mode():
        raise ValueError('Boot export requires the SoftMotion Win software target outside IDE Simulation')
    app = find_app(project)
    if app is None or not any(unicode(item.guid) == unicode(app.guid) for item in device.get_children(True)):
        raise ValueError('Active application does not belong to the software controller')
    diagnostics = op_compile(project, {})
    if diagnostics['error_count']:
        return dict(diagnostics, generated=False, online_verified=False)
    directory = tempfile.mkdtemp(prefix='software-boot-', dir=os.path.dirname(os.path.abspath(PROJECT_PATH)))
    app.create_boot_application(os.path.join(directory, 'Application.app'), False, False)
    files = []
    for name in ('Application.app', 'Application.crc'):
        filename = os.path.join(directory, name)
        with open(filename, 'rb') as stream:
            content = stream.read()
        if not content:
            raise RuntimeError('Native boot export is empty: ' + name)
        files.append({'name':name, 'path':filename, 'bytes':len(content), 'sha256':hashlib.sha256(content).hexdigest()})
    return dict(diagnostics, generated=True, directory=directory, files=files,
                target=identity, application_guid=unicode(app.guid), online_verified=False)
