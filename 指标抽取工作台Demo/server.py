"""Local source-backed Xiuqing extraction.
File inventory, template/OWL reading and workbook export are real operations.
"""
import json
import os
import re
import subprocess
import sys
import uuid
import copy
from threading import Lock
import xml.etree.ElementTree as ET
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import openpyxl
from real_extract import extract
from stages import STAGES, classify_stage
from projects import project_list, apply_snapshot, combine, validate_config, contract_key
from cost_reports import reports, reveal_source, reveal_report_ref
from verification import verification, reveal_candidate

APP = Path(__file__).resolve().parent
ROOT = APP.parent
PORT = int(os.environ.get('GRID_DEMO_PORT', '18864'))
NODE = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
SUPPORTED = {'.xls', '.xlsx', '.docx', '.pdf', '.png', '.jpg', '.jpeg'}
CHECKS={}
CHECK_LOCK=Lock()
NS = {'owl':'http://www.w3.org/2002/07/owl#', 'rdf':'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'gte':'https://example.org/grid-tech-economic#'}

def norm(text):
    return re.sub(r'\s+', '', str(text or ''))

def owl_definitions(path):
    root = ET.parse(path).getroot()
    result = []
    for node in root.findall('owl:NamedIndividual', NS):
        if not any(t.get('{'+NS['rdf']+'}resource','').endswith('#IndicatorDefinition') for t in node.findall('rdf:type', NS)):
            continue
        result.append({'id':node.get('{'+NS['rdf']+'}about','').split('#')[-1],
                       **{k:node.findtext('gte:'+k, default='', namespaces=NS) for k in ('name','identifier','definitionText','standardUnit','applicability')}})
    if not result:
        raise ValueError('OWL 中未找到本项目使用的 IndicatorDefinition 指标定义，请选择包含指标实例的 OWL。')
    return result

def template_data(path):
    book = openpyxl.load_workbook(path, data_only=False)
    sheets = []
    for ws in book:
        if ws.max_column > 500:
            raise ValueError('模板超过 500 列，请先缩小有效区域。')
        first = next((r for r in range(2,min(ws.max_row,20)+1) if isinstance(ws.cell(r,1).value,(int,float))), None)
        count = first-1 if first else min(ws.max_row,6)
        if not count:
            continue
        merges = [m for m in ws.merged_cells.ranges if m.max_row <= count]
        ancestors = {}
        for m in merges:
            for r in range(m.min_row,m.max_row+1):
                for c in range(m.min_col,m.max_col+1):
                    ancestors[(r,c)] = ws.cell(m.min_row,m.min_col)
        fields=[]
        for c in range(1,ws.max_column+1):
            chain=[]; comments=[]
            for r in range(2,count+1):
                cell=ancestors.get((r,c),ws.cell(r,c))
                value=norm(cell.value)
                if value and (not chain or chain[-1]!=value): chain.append(value)
                if cell.comment and cell.comment.text not in comments: comments.append(cell.comment.text)
            fields.append({'column':openpyxl.utils.get_column_letter(c),'chain':chain,'label':' / '.join(chain), 'comment':'\n'.join(comments)})
        cells=[]
        for row in ws.iter_rows(min_row=1,max_row=count):
            for cell in row:
                if cell.value is None: continue
                color=cell.fill.fgColor
                cells.append({'address':cell.coordinate,'row':cell.row,'column':cell.column,'value':cell.value if isinstance(cell.value,(str,int,float,bool)) else str(cell.value),
                              'fill':'#'+color.rgb[-6:] if color.type=='rgb' and color.rgb not in ('00000000','00FFFFFF') else None,
                              'fontSize':cell.font.sz or 10,'bold':bool(cell.font.bold)})
        sheets.append({'name':ws.title,'headerRows':count,'columns':ws.max_column,'fields':fields,'cells':cells,
                       'merges':[{'range':str(m),'r1':m.min_row,'r2':m.max_row,'c1':m.min_col,'c2':m.max_col} for m in merges],
                       'widths':[max(70,min(260,(ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width or 13)*7)) for c in range(1,ws.max_column+1)]})
    book.close()
    return sheets

def inspect_inputs(payload):
    folder=Path(payload['folder']); template=Path(payload['template']); owl=Path(payload['owl'])
    if not folder.is_dir(): raise ValueError('工程文件夹不存在。')
    if not template.is_file() or template.suffix.lower()!='.xlsx': raise ValueError('请选择 .xlsx 格式的 Excel 模板。')
    if not owl.is_file() or owl.suffix.lower() not in ('.owl','.rdf','.xml'): raise ValueError('请选择有效的 OWL / RDF/XML 文件。')
    files=[]; skipped=0
    for base,dirs,names in os.walk(folder):
        dirs[:]=[d for d in dirs if d not in ('.git','node_modules','.venv','models','outputs')]
        for name in names:
            p=Path(base)/name
            if p.suffix.lower() not in SUPPORTED or name.startswith('~$'):
                skipped+=1;continue
            try: size=p.stat().st_size
            except OSError: continue
            relative=str(p.relative_to(folder))
            files.append({'name':name,'path':relative,'ext':p.suffix.lower()[1:],'size':size,**classify_stage(relative)})
        if len(files)>5000: raise ValueError('文件超过 5000 份，请选择具体工程目录。')
    defs=owl_definitions(owl); sheets=template_data(template)
    aliases={'安装':'安装工程费','安装工程费合计':'安装工程费','建筑':'建筑工程费','建筑费合计':'建筑工程费','建筑工程费合计':'建筑工程费','设备':'设备购置费','设备费合计':'设备购置费','其他费用合计':'其他费用','建场费合计':'建设场地征用及清理费','场地平整费用（万元）':'场地平整费用','静态投资':'静态投资','动态投资':'动态投资'}
    aliases.update({'本期台数（三相）':'主变数量','其中，全站征地面积（亩）':'全站征地面积','地基处理费用（万元）':'地基处理费用'})
    for s in sheets:
        for field in s['fields']:
            leaf=field['chain'][-1] if field['chain'] else ''
            name=aliases.get(leaf,leaf)
            if '本期出线回数' in field['label'] and leaf=='高压侧': name='高压侧出线回路'
            if '建筑面积（m2）' in field['chain'] and leaf=='全站': name='建筑物面积'
            matches=[d for d in defs if norm(d['name'])==name]
            expected={'变电工程':'变电站','架空线路':'架空','电缆线路':'电缆','通信设备':'通信','通信光缆':'通信'}.get(s['name'])
            typed=[d for d in matches if expected and expected in d['applicability']]
            matches=typed if expected else matches
            field['matches']=matches
    return {'folder':str(folder),'project':folder.name,'template':str(template),'owl':str(owl),'files':files,'skipped':skipped,'definitions':defs,'sheets':sheets}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def respond(self,value,status=200):
        data=json.dumps(value,ensure_ascii=False).encode('utf8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path=='/api/verification':
            try: return self.respond(verification())
            except Exception as e: return self.respond({'error':str(e)},400)
        if self.path=='/api/cost-reports':
            try: return self.respond(reports())
            except Exception as e: return self.respond({'error':str(e)},400)
        if self.path=='/api/defaults':
            return self.respond({'version':'multi-project-v1','projects':project_list(),'folder':project_list()[1]['folder'],'template':str(ROOT/'2025主网项目指标参考(1).xlsx'),'owl':str(ROOT/'Algorithm/grid_tech_economic_framework_v3(1).owl'),'model':'Qwen3.5-9B','modelExists':(ROOT/'models/Qwen3.5-9B/config.json').is_file()})
        if self.path.startswith('/download/'):
            name=self.path.split('/')[-1]
            if not re.fullmatch(r'[a-f0-9]{32}\.xlsx',name): return self.respond({'error':'无效下载地址'},404)
            path=APP/'outputs'/name; mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            names={'/':'index.html','/app.js':'app.js','/verification.js':'verification.js','/style.css':'style.css'}
            if self.path not in names: return self.respond({'error':'not found'},404)
            path=APP/names[self.path];mime={'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[path.suffix[1:]]
        if not path.is_file(): return self.respond({'error':'文件不存在'},404)
        data=path.read_bytes(); self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_POST(self):
        if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):
            return self.respond({'error':'跨域请求被拒绝'},403)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>100000: raise ValueError('请求过大')
            body=json.loads(self.rfile.read(length) or '{}')
            if self.path=='/api/reveal-report-ref':
                return self.respond(reveal_report_ref(body.get('projectId'),body.get('findingIndex'),body.get('refIndex')))
            if self.path=='/api/reveal-candidate':
                return self.respond(reveal_candidate(body.get('projectId'),body.get('column'),body.get('index')))
            if self.path=='/api/reveal-source':
                return self.respond(reveal_source(body.get('projectId'),body.get('column')))
            if self.path=='/api/pick':
                kind=body.get('kind')
                if kind not in ('folder','template','owl'): raise ValueError('无效选择类型')
                r=subprocess.run([sys.executable,str(APP/'picker.py'),kind,str(body.get('current',''))],capture_output=True,text=True,encoding='utf8',timeout=300,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                if r.returncode: raise ValueError('文件选择窗口无法打开，请在输入框粘贴路径。')
                return self.respond({'path':r.stdout.strip()})
            if self.path=='/api/inspect':
                info=inspect_inputs(body);validate_config(info)
                info['contractKey']=contract_key(info);info['checkToken']=uuid.uuid4().hex
                with CHECK_LOCK:
                    if len(CHECKS)>=128:CHECKS.pop(next(iter(CHECKS)))
                    CHECKS[info['checkToken']]=copy.deepcopy(info)
                return self.respond(info)
            if self.path=='/api/result':
                with CHECK_LOCK:checked=copy.deepcopy(CHECKS.get(body.get('checkToken')))
                if not checked:raise ValueError('请先检查配置。')
                if any(str(Path(body.get(k,'')).resolve())!=str(Path(checked[k]).resolve()) for k in ('folder','template','owl')) or contract_key(checked)!=checked['contractKey']:
                    raise ValueError('配置已改变，请重新检查。')
                info=apply_snapshot(checked);info['resultId']=uuid.uuid4().hex
                (APP/'outputs'/('result_'+info['resultId']+'.json')).write_text(json.dumps(info,ensure_ascii=False),encoding='utf8')
                return self.respond(info)
            if self.path=='/api/export':
                ids=body.get('resultIds',[])
                if not isinstance(ids,list) or not 1<=len(ids)<=5:raise ValueError('请选择1至5个已完成工程导出。')
                results=[]
                for rid in ids:
                    if not isinstance(rid,str) or not re.fullmatch(r'[a-f0-9]{32}',rid):raise ValueError('无效结果凭据。')
                    path=APP/'outputs'/('result_'+rid+'.json')
                    if not path.is_file():raise ValueError('结果不存在，请重新提取。')
                    results.append(json.loads(path.read_text(encoding='utf8')))
                info=combine(results)
                key=uuid.uuid4().hex; job=APP/'outputs'/f'{key}.json'; output=APP/'outputs'/f'{key}.xlsx'
                job.write_text(json.dumps(info,ensure_ascii=False),encoding='utf8')
                r=subprocess.run([str(NODE),str(APP/'export.mjs'),str(job),str(output)],capture_output=True,text=True,encoding='utf8',timeout=180)
                if r.returncode: raise ValueError('Excel 导出失败：'+r.stderr[-400:])
                return self.respond({'url':'/download/'+output.name,'path':str(output)})
            self.respond({'error':'not found'},404)
        except Exception as e: self.respond({'error':str(e)},400)

if __name__=='__main__':
    print(f'http://127.0.0.1:{PORT}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
