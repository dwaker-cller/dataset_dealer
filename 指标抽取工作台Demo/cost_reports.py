"""Five curated cost reports for the local demonstration."""
import json
import subprocess
from pathlib import Path
from projects import APP, ROOT, project_list, digest

COST_COLUMNS = set('CI CJ CK CL CO CQ CR CS CT CU CV CW CX CY CZ DA DB DC DD DG DH DI DJ DK DL DM DN DO DP DQ DR DS DT DU DV DW EA EB EC ED EE EF EG EH EI EL EM EN EO EP EQ ER ES ET EU EX EY EZ FA FB FC FD FE FF FG FH FI FL FM FN FO FP FQ FR FT FU FV FW FX FY FZ GA GB GC GD GE GF GG GH GI GJ GK GL GM GN GO'.split())

def snapshot():
    return json.loads((APP/'outputs/multi_project_records.json').read_text(encoding='utf8'))

def source_path(project_id, column):
    project=next((p for p in project_list() if p['id']==project_id),None)
    if not project or column not in COST_COLUMNS: raise ValueError('请选择五工程中的费用来源。')
    entry=snapshot()['projects'][project_id]['records'].get(column)
    if not entry: raise ValueError('该费用暂无来源。')
    evidence=entry['evidence'];path=(ROOT/evidence['file']).resolve()
    if not path.is_relative_to(Path(project['folder']).resolve()): raise ValueError('来源超出工程范围。')
    if not path.is_file(): raise ValueError('来源文件不存在，可能已移动。')
    if digest(path)!=evidence['sha256']: raise ValueError('来源文件已变化，请重新核对报告。')
    return path

def reveal_source(project_id,column):
    path=source_path(project_id,column)
    subprocess.Popen(['explorer.exe','/select,',str(path)])
    return {'opened':True}

def reveal_report_ref(project_id,finding_index,ref_index):
    report=next(r for r in reports()['reports'] if r['id']==project_id)
    evidence=report['documentFindings'][int(finding_index)]['refs'][int(ref_index)]
    subprocess.Popen(['explorer.exe','/select,',str((ROOT/evidence['file']).resolve())])
    return {'opened':True}

def reports():
    data=json.loads((APP/'outputs/cost_reports.json').read_text(encoding='utf8'))
    if data['snapshotHash']!=digest(APP/'outputs/multi_project_records.json'):
        raise ValueError('费用数据已更新，请重新整理报告。')
    checked=set()
    for report in data['reports']:
        for item in report['sources']:
            key=item['file']
            if key not in checked:
                source_path(report['id'],item['column']);checked.add(key)
    findings_path=APP/'outputs/document_findings.json'
    if findings_path.exists():
        findings=json.loads(findings_path.read_text(encoding='utf8'))
        from verification import verification
        decisions={p['id']:p for p in verification()['projects']}
        for report in data['reports']:
            if report['id'] not in findings:continue
            report['documentFindings']=findings[report['id']]
            for finding in report['documentFindings']:
                for e in finding['refs']:
                    path=(ROOT/e['file']).resolve()
                    folder=Path(next(p['folder'] for p in project_list() if p['id']==report['id'])).resolve()
                    if not path.is_relative_to(folder) or not path.is_file() or digest(path)!=e['sha256']:raise ValueError('报告引用资料已变化，请重新分析。')
            decision=next(i for i in decisions[report['id']]['items'] if i['column']==report['totalColumn'])
            report['totalApproved']=decision['status']=='已核验'
            dynamic_column='FD' if report['totalColumn']=='FB' else 'DV'
            dynamic_decision=next((i for i in decisions[report['id']]['items'] if i['column']==dynamic_column),None)
            report['dynamicApproved']=bool(dynamic_decision and dynamic_decision['status']=='已核验')
            withheld={i['column'] for i in decisions[report['id']]['items'] if i['status']!='已核验'}
            report['sources']=[e for e in report['sources'] if e['column'] not in withheld]
            if not report['totalApproved']:
                report['summary']='静态投资存在未解决的来源差异，暂不回填，也不计算费用占比。'
                report['sections']=[]
                report['sources']=[e for e in report['sources'] if e['column']!=report['totalColumn']]
    return data
