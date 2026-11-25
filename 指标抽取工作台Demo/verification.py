"""Read curated verification evidence; invalidate it when sources change."""
import json
from projects import APP, ROOT, digest, project_list

def may_fill(item):
    return bool(item and item.get('status')=='已核验')

def reveal_candidate(project_id,column,index):
    import subprocess
    from pathlib import Path
    project=next(p for p in verification()['projects'] if p['id']==project_id)
    item=next(i for i in project['items'] if i['column']==column)
    evidence=item['candidates'][int(index)]
    path=(ROOT/evidence['file']).resolve()
    folder=Path(next(p['folder'] for p in project_list() if p['id']==project_id)).resolve()
    if not path.is_relative_to(folder) or not path.is_file() or digest(path)!=evidence['sha256']:raise ValueError('候选来源已变化或无效')
    subprocess.Popen(['explorer.exe','/select,',str(path)])
    return {'opened':True}

def classify(source_current, checks_passed, conflict):
    if not source_current: return '待核验'
    if conflict: return '来源冲突'
    return '已核验' if checks_passed else '待核验'

def verification():
    reviewed=APP/'outputs/candidate_review.json'
    data=json.loads((reviewed if reviewed.exists() else APP/'outputs/verification.json').read_text(encoding='utf8'))
    current=json.loads((APP/'outputs/multi_project_records.json').read_text(encoding='utf8'))
    hashes={}
    for project in data['projects']:
        folder=next(p['folder'] for p in project_list() if p['id']==project['id'])
        for item in project['items']:
            e=item['evidence'];p=(ROOT/e['file']).resolve()
            if str(p) not in hashes:
                from pathlib import Path
                hashes[str(p)]=digest(p) if p.is_file() and p.is_relative_to(Path(folder).resolve()) else None
            same=hashes[str(p)]==e['sha256']
            if not item.get('candidateOnly'):
                same=same and current['projects'][project['id']]['records'].get(item['column'],{}).get('evidence')==e
            for candidate in item.get('candidates',[]):
                cp=(ROOT/candidate['file']).resolve()
                from pathlib import Path
                if not cp.is_relative_to(Path(folder).resolve()) or not cp.is_file() or digest(cp)!=candidate['sha256']:same=False
            item['status']=classify(same,item['checksPassed'],bool(item['conflicts']))
            if not same:item['reason']='来源或当前取值记录已变化，原核验结论失效，请重新核验。'
        project['counts']={s:sum(i['status']==s for i in project['items']) for s in ['已核验','待核验','来源冲突']}
    return data
