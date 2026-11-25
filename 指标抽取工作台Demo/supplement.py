"""Validated, source-fingerprinted Xiuqing supplementary evidence replay."""
import json, hashlib
from pathlib import Path
from decimal import Decimal

OUT=Path(__file__).resolve().parents[1]/'outputs/xiuqing_supplement_20261004'

def enrich(info):
    path=OUT/'supplement.json'
    if not path.exists(): return info
    data=json.loads(path.read_text(encoding='utf8'))
    sheet=info['sheets'][0]; fields={f['column']:f for f in sheet['fields']}
    folder=Path(info['folder']).resolve(); hashes={}; x=info['extraction']; added=0
    def valid(r):
        p=Path(r['file']).resolve()
        if not p.is_relative_to(folder) or not p.is_file(): return False
        if str(p) not in hashes: hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        return hashes[str(p)]==r.get('sha256')
    for r in data['records']:
        f=fields.get(r['column'])
        if not f or f.get('evidence') or f['label']!=r['label'] or not valid(r): continue
        matches=f['matches']
        compatible=lambda d: d['standardUnit']==r['unit'] or (d['standardUnit']=='元' and r['unit']=='万元')
        if matches and not all('变电站' in d['applicability'] and compatible(d) for d in matches):
            x['issues'].append(r['column']+'：补充证据与OWL类型/单位不兼容，未回填。');continue
        ev=dict(r,route='OWL 约束' if matches else '模板字段',definitions=[d['id'] for d in matches],
                templateField=f['label'],templateCell=f['column']+str(sheet['headerRows']+1))
        if r['unit']=='万元':
            ev['standardUnit']='元';ev['standardValue']=str(Decimal(r['rawValue']) if r['sourceUnit']=='元' else Decimal(str(r['value']))*10000)
        f['evidence']=ev;sheet['rows'][0][sheet['fields'].index(f)]=r['value'];added+=1
    conflicts=[]
    for c in data['conflicts']:
        f=fields.get(c['column'])
        if not f or not f.get('evidence') or not valid(c):continue
        c=dict(c,retainedValue=f['evidence']['value'],templateField=f['label'],templateCell=f['column']+str(sheet['headerRows']+1))
        f['conflicts']=[c];conflicts.append(c)
    for f in sheet['fields']:
        if f.get('evidence'):continue
        reason='已扩大文字层与表格检索，但尚未取得满足工程对象、阶段、单位及字段口径的唯一证据；部分扫描页尚待OCR。'
        status='证据不足'
        if f['column']=='H':status='编码口径不符';reason='决算来源为15位ERP单体编号，模板要求14位工程编码，不能直接代填。'
        elif f['column'] in ('DL','DM'):status='费用未拆分';reason='来源仅可靠列示合计勘察设计费，子行0不代表实际费用为0，无法拆分。'
        elif '施工图' in f['label'] and ('预算' in f['label']):
            status='预算证据不足';reason='本轮取得的评审意见未提供对应预算明细；目录含zwzj预算文件，按要求尚未启用，不能用初设或决算代填。'
        f.update(missingReason=reason,missingStatus=status)
    evs=[f['evidence'] for f in sheet['fields'] if f.get('evidence')]
    x.update(filled=len(evs),missing=sheet['rows'][0].count('未包含'),supplemented=added,
        owlCount=sum(e['route']=='OWL 约束' for e in evs),templateCount=sum(e['route']=='模板字段' for e in evs),
        conflicts=conflicts,sources=list(dict.fromkeys(e['file'] for e in evs)),model=data['model'],
        method='程序解析Excel/PDF，重点报告采用本地OCR；Qwen3.5-9B离线完成5项字段语义选证，程序校验引用、数值、单位后回填。页面重读时复用已校验结果，并核对源文件SHA256，不重复调用模型。',
        scope='已对全目录可支持格式执行原生解析，检索58份PDF共920页文字层；重点审计报告、管理建议书完成OCR。尚未完成所有扫描页OCR，zwzj继续跳过。')
    x['issues']+=data['issues']
    coverage=OUT/'coverage.json'
    if coverage.exists():x['coverage']=json.loads(coverage.read_text(encoding='utf8'))
    return info
