"""Five-project, source-fingerprinted result replay for the demonstration UI."""
import copy
import hashlib
import json
from pathlib import Path

APP=Path(__file__).resolve().parent
ROOT=APP.parent
CATALOG=[('maoshan','常州茅山','2026-1-418-常州茅山500千伏主变扩建工程'),
         ('xiuqing','扬州秀清','2026-3-463-扬州秀清220kV输变电工程'),
         ('peixian','徐州沛县','2026-4-568-徐州沛县110千伏变电站改造工程'),
         ('puti','连云港菩提','2026-7-638-连云港菩提110kV输变电工程'),
         ('chuanshan','江苏镇江圌山','2025-2-45-江苏镇江圌山220kV输变电工程')]

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def project_list():
    return [dict(id=i,name=n,folder=str(ROOT/'造价数据'/d)) for i,n,d in CATALOG]

def contract_key(info):
    return digest(info['template'])+':'+digest(info['owl'])

def identify(folder):
    p=Path(folder).resolve()
    hits=[v for v in project_list() if p==Path(v['folder']).resolve() or p==Path(v['folder']).resolve()/Path(v['folder']).name]
    if len(hits)!=1:raise ValueError('请在“造价数据”目录下选择一个具体工程文件夹。')
    return hits[0]

def validate_config(info):
    identify(info['folder'])
    sheet=next((s for s in info['sheets'] if s['name']=='变电工程'),None)
    expected=json.loads((APP/'outputs/multi_project_records.json').read_text(encoding='utf8'))['fields']
    if not sheet or [(f['column'],f['label'],f['comment']) for f in sheet['fields']]!=[(f['column'],f['label'],f['comment']) for f in expected]:
        raise ValueError('展示结果对应当前197列变电工程模板，请选择原配套模板；不支持将预置结果套入不同字段口径。')
    if digest(info['owl'])!=digest(ROOT/'Algorithm/grid_tech_economic_framework_v3(1).owl'):
        raise ValueError('本演示请使用配套 OWL 指标标准。')

def apply_snapshot(info):
    validate_config(info)
    project=identify(info['folder'])
    record=json.loads((APP/'outputs/multi_project_records.json').read_text(encoding='utf8'))['projects'][project['id']]
    decisions=None
    if (APP/'outputs/candidate_review.json').exists():
        from verification import verification,may_fill
        decisions={i['column']:i for p in verification()['projects'] if p['id']==project['id'] for i in p['items']}
    sheet=next(s for s in info['sheets'] if s['name']=='变电工程')
    values=['未包含']*sheet['columns'];sources={};count=0
    for index,f in enumerate(sheet['fields']):
        f.update(evidence=None,missingReason='本演示尚未整理出该字段的可回填证据，不代表源资料不存在。',missingStatus='证据不足')
        if project['id']=='peixian' and f['column']=='S':
            f.update(missingReason='工程名称为改造，竣工概况表建设性质写新建，口径冲突尚未解决，暂不回填。',missingStatus='来源冲突')
        if f['column']=='A':f['missingReason']='序号由当前累计顺序生成，不属于来源指标。'
        entry=record['records'].get(f['column'])
        if decisions is not None and f['column'] in decisions and not may_fill(decisions[f['column']]):
            decision=decisions[f['column']]
            f.update(missingReason=decision['reason'],missingStatus=decision['status'],candidates=copy.deepcopy(decision.get('candidates',[])),conflicts=copy.deepcopy(decision.get('conflicts',[])))
            continue
        if not entry:continue
        e=copy.deepcopy(entry['evidence']);p=ROOT/e['file']
        if not p.resolve().is_relative_to(Path(project['folder']).resolve()):raise ValueError('证据不属于当前工程。')
        if str(p) not in sources:
            if not p.is_file():raise ValueError('预置证据来源缺失：'+p.name)
            sources[str(p)]=digest(p)
        if sources[str(p)]!=e['sha256']:raise ValueError('来源文件已变化，请重新整理展示结果：'+p.name)
        e.update(file=str(p),templateField=f['label'],templateCell=f['column']+str(sheet['headerRows']+1))
        f['evidence']=e;values[index]=e['value'];count+=1
        if entry.get('conflicts'):
            f['conflicts']=copy.deepcopy(entry['conflicts'])
            for c in f['conflicts']:
                cp=ROOT/c['file']
                if not cp.is_file() or digest(cp)!=c['sha256']:raise ValueError('冲突来源已变化：'+cp.name)
                c['file']=str(cp)
    # Sequence is UI metadata, not a source-derived engineering indicator.
    values[0]=1
    sheet['rows']=[values]
    sheet['rowFields']=[copy.deepcopy(sheet['fields'])]
    sheet['rowProjects']=[project['name']]
    info.update(sheets=[sheet],activeSheet=sheet['name'],projectId=project['id'],projectName=project['name'],contractKey=contract_key(info))
    info['extraction']=dict(mode='预置结果展示',method='展示根据真实资料预先整理的结果；本次核验来源指纹，不新增 OCR 或模型推理。',
        scope=record['scope'],taxBasis=record['taxBasis'],sources=list(sources),filled=count,
        owlCount=sum(f.get('evidence',{}).get('route')=='OWL 约束' for f in sheet['fields'] if f.get('evidence')),
        templateCount=sum(f.get('evidence',{}).get('route')!='OWL 约束' for f in sheet['fields'] if f.get('evidence')),
        missing=values.count('未包含'),issues=record.get('issues',[]),conflicts=[c for f in sheet['fields'] for c in f.get('conflicts',[])])
    return info

def combine(results):
    if not results:raise ValueError('请先完成至少一个工程。')
    if len({r['contractKey'] for r in results})!=1:raise ValueError('模板或 OWL 已改变，请清空累计结果后开始新批次。')
    unique={r['projectId']:r for r in results}
    out=copy.deepcopy(next(iter(unique.values())))
    s=out['sheets'][0];s.update(rows=[],rowFields=[],rowProjects=[])
    for i,r in enumerate(unique.values()):
        original=r['sheets'][0];row=copy.deepcopy(original['rows'][0]);row[0]=i+1
        fields=copy.deepcopy(original['fields'])
        for f in fields:
            cell=f['column']+str(s['headerRows']+i+1)
            if f.get('evidence'):f['evidence']['templateCell']=cell
            for c in f.get('conflicts',[]):c['templateCell']=cell
        s['rows'].append(row);s['rowFields'].append(fields);s['rowProjects'].append(r['projectName'])
    out['extraction']['scope']='五工程累计展示；来源为真实资料预置结果，每行独立保存取值依据。'
    return out
