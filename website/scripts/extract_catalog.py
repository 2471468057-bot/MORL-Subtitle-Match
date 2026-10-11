"""Read public literals with AST only. Never import the desktop application."""
import ast
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'website'
sources = {}

def tree(rel):
    raw = (ROOT / rel).read_bytes()
    sources[rel] = hashlib.sha256(raw).hexdigest()
    return ast.parse(raw.decode('utf-8-sig'))

def assignment(module, name):
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
        if isinstance(node, ast.AnnAssign) and getattr(node.target, 'id', None) == name:
            return node.value
    raise ValueError(name)

def records(module, class_name, value):
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    fields = [n for n in cls.body if isinstance(n, ast.AnnAssign)]
    defaults = {n.target.id: ast.literal_eval(n.value) for n in fields if n.value}
    names = [n.target.id for n in fields]
    def record(node):
        return defaults | dict(zip(names, map(ast.literal_eval, node.args))) | {k.arg: ast.literal_eval(k.value) for k in node.keywords}
    if isinstance(value, ast.Dict):
        return {ast.literal_eval(k): record(v) for k, v in zip(value.keys, value.values)}
    return [record(n) for n in value.elts]

workshop = tree('twobyteasr/model_workshop.py')
models = records(workshop, 'WorkshopModel', assignment(workshop, 'MODELS'))
metadata = ast.literal_eval(assignment(tree('twobyteasr/model_evaluation_metadata.py'), '_TECHNICAL_PROFILES'))
copy_tree = tree('twobyteasr/model_task_metadata.py')
copy = records(copy_tree, 'ModelCopy', assignment(copy_tree, 'MODEL_COPY'))
api = ast.literal_eval(assignment(tree('twobyteasr/ui.py'), 'ASR_API_PRESETS'))
defaults = ast.literal_eval(assignment(tree('twobyteasr/settings.py'), 'DEFAULT_SETTINGS'))
requirements = ast.literal_eval(assignment(workshop, 'ROLE_CAPABILITY_REQUIREMENTS'))

# Public endpoints only. Source contains a tenant-specific Filetrans host.
public_hosts = ('dashscope.aliyuncs.com', 'api.groq.com', 'api.openai.com', 'openrouter.ai', 'iat.cn-huabei-1.xf-yun.com')
for preset in api.values():
    from urllib.parse import urlparse
    if urlparse(preset['url']).hostname not in public_hosts:
        preset['url'] = 'https://example.invalid/v1/audio/transcriptions'

output = []
for m in models:
    profile = metadata.get(m['key'], {})
    roles = [role for role, backend in m['adapter_bindings']
             if m['runtime_available'] and any(set(req) <= set(m['asr_capabilities']) for req in requirements[role])]
    fields = ('key', 'name', 'summary', 'mode', 'size', 'description', 'languages', 'logo_asset', 'api_preset', 'install_keys', 'runtime_available', 'asr_capabilities', 'adapter_bindings')
    item = {key: m[key] for key in fields}
    item.update(roles=roles, groups=roles+(['api'] if m['api_preset'] else []) if roles else ['weights'], online=bool(m['api_preset']))
    item['copy'] = copy.get(m['key'], {'summary': m['summary'], 'limitations': ''})
    item['technical'] = {k: profile[k] for k in ('purpose','principles','limits','io','url','hf','modelscope','paper','official') if k in profile}
    item['verification'] = '目录已接入；本网页未进行后端实测'
    if m['key'] == 'omni_asr_llm_7b':
        item['verification'] = '仅权重；上游运行库不支持原生 Windows 推理'
    elif m['key'] in ('spark_asr_v2', 'qwen31_flash', 'qwen31_filetrans'):
        item['verification'] = '实验接口；实际服务端到端验证待完成'
    # Generic icon instead of assigning another vendor's logo to custom ASR.
    if m['key'] == 'custom_asr_api': item['logo_asset'] = None
    item['config'] = api.get(m['api_preset'], {})
    item['recommended'] = bool(m.get('recommended'))
    output.append(item)

# Module-level constants, evaluated one by one (no import of the module).
def constants(module):
    space = {}
    for node in module.body:
        target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else getattr(node, 'target', None)
        if not isinstance(target, ast.Name) or getattr(node, 'value', None) is None:
            continue
        try:
            space[target.id] = eval(compile(ast.Expression(node.value), '<const>', 'eval'), {'__builtins__': {}}, space)
        except Exception:
            pass
    return space

# Recognition plans: the same six goals as the desktop “先选目标”.
plans_tree = tree('twobyteasr/recognition_plans.py')
plans = records(plans_tree, 'RecognitionPlan', assignment(plans_tree, 'RECOGNITION_PLANS'))

# Five themes: tokens plus each theme's role and zone colours.
theme_tree = tree('twobyteasr/ui_theme.py')
theme_names = constants(theme_tree)
themes = {}
for key_node, call in zip(assignment(theme_tree, 'THEMES').keys, assignment(theme_tree, 'THEMES').values):
    fields = {k.arg: eval(compile(ast.Expression(k.value), '<theme>', 'eval'), {'__builtins__': {}}, theme_names) for k in call.keywords}
    themes[ast.literal_eval(key_node)] = {k: v for k, v in fields.items() if k != 'labels'} | {'name': fields['labels']['zh']}
theme_class = next(n for n in theme_tree.body if isinstance(n, ast.ClassDef) and n.name == 'ThemeDefinition')
def theme_property(name):
    fn = next(n for n in theme_class.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return [n for n in ast.walk(fn) if isinstance(n, ast.Dict)]
role_colors = max((ast.literal_eval(d) for d in theme_property('role_colors')), key=len)
zone_fn = next(n for n in theme_class.body if isinstance(n, ast.FunctionDef) and n.name == 'zone_colors')
zone_if = next(n for n in zone_fn.body if isinstance(n, ast.If))
zone = (zone_if.body[0].value, zone_fn.body[-1].value)  # (warm, dark themes)
for key, theme in themes.items():
    theme['roles'] = role_colors.get(key, role_colors['grape'])
    theme['zones'] = ast.literal_eval(zone[0] if key == 'warm' else zone[1])
    theme['accent_text'] = {'grape': '#ec8db0', 'plum': '#a9d1a6', 'lavender': '#dcc3f7', 'slate': '#f2b896'}.get(key, theme['accent'])

# 2ByteASR reference index: the same scene rule as the Model Workshop cards.
bench_tree = tree('twobyteasr/model_benchmarks.py')
bench = constants(bench_tree)
def _ref(score, basis, label, reason, detail, sources, approx=None):
    return {'score': int(score), 'basis': basis, 'label': label, 'reason': reason,
            'approx': approx if approx is not None else basis in bench['_ESTIMATE_BASES']}
bench['_ref'] = _ref
reference_index = eval(compile(ast.Expression(assignment(bench_tree, '_REFERENCE_INDEX')), '<ref>', 'eval'), {'__builtins__': {}}, bench)
def reference(m, kind):
    scene = 'align' if 'ASR_TEXT' not in m['asr_capabilities'] and 'ALIGNMENT' in m['asr_capabilities'] else \
        'en' if tuple(m['languages']) == ('English',) else bench['DEFAULT_SCENE']
    record = reference_index.get((m['key'], kind))
    if not record or scene in (record.get('unsupported') or {}):
        return None
    entry = (record.get('scenes') or {}).get(scene) or record.get('default')
    return entry and dict(entry, scene=scene)
for m, item in zip(models, output):
    item['reference'] = {'accuracy': reference(m, 'accuracy'), 'speed': reference(m, 'speed'),
                         'caption': '对齐精度' if 'ASR_TEXT' not in m['asr_capabilities'] and 'ALIGNMENT' in m['asr_capabilities'] else '转写准确度'}

version_info = json.loads((ROOT/'2byteasr_version.json').read_text('utf-8-sig'))
snapshot = dict(schema=2, date='2026-10-09', version=version_info['version'], channel=version_info.get('channel', ''),
                scope='当前开发工作区目录；与同版本号安装附件可能存在差异', models=output,
                plans=plans, themes=themes,
                reference_note='2ByteASR 参考指数：1–100 相对选型参考，不是识别正确率。版本 ' + bench['REFERENCE_INDEX_VERSION'],
                defaults={section: defaults[section] for section in ('switches','performance','ui')},
                api_presets=api,
                rules={'shared_api_provider': True, 'optional_roles':['timeline','review','speaker'],
                       'aligner_needs_text':True, 'speaker_default':'single'})
(WEB/'public/data/catalog.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), 'utf-8')
(WEB/'internal/source-manifest.json').write_text(json.dumps(dict(date='2026-10-09',sources=sources),ensure_ascii=False,indent=2),'utf-8')
for name in ('2byteasr-icon-transparent.png',):
    shutil.copyfile(ROOT/'assets'/name, WEB/'public/assets'/name)
shutil.copytree(ROOT/'assets/model_logos', WEB/'public/assets/model-logos', dirs_exist_ok=True)
print(json.dumps({'catalog_entries':len(output),'selectable':sum(bool(m['roles']) for m in output),'online':sum(m['online'] for m in output)},ensure_ascii=False))
