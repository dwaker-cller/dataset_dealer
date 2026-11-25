"""Evidence-backed Xiuqing adapter: source values, never reference-template rows."""
import hashlib
import re
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import openpyxl
import pdfplumber
from pypdf import PdfReader

def clean(v): return re.sub(r'\s+', '', str(v or ''))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def extract(info):
    root=Path(info['folder'])
    sources=list(root.rglob('01-1-秀清220千伏变电站新建工程-审定决算表.xlsx'))
    pdfs=list(root.rglob('苏电建初设批复*.pdf'))
    if len(sources)!=1: raise ValueError('本轮已接通秀清工程。请选择包含唯一“01-1-秀清…审定决算表.xlsx”的工程目录。')
    sheet=next((s for s in info['sheets'] if s['name']=='变电工程'),None)
    if sheet is None: raise ValueError('模板中缺少“变电工程”工作表。')
    # Only the requested substation worksheet is filled/exported in this release.
    info['sheets']=[sheet]
    values=['未包含']*sheet['columns']; evidence={}; issues=[]
    book=openpyxl.load_workbook(sources[0],data_only=True,read_only=True)
    source_hash=digest(sources[0])
    tax='审定决算实际价值，抵扣增值税另列；本轮按此净额口径回填，不与含税概算直接计算节约率。'
    def target(suffix,stage=None):
        found=[(i,f) for i,f in enumerate(sheet['fields']) if f['label'].endswith(suffix) and (stage is None or f['chain'][0]==stage)]
        if len(found)!=1: raise ValueError('模板字段缺失或不唯一：'+str(stage)+' / '+suffix)
        return found[0]
    def put(suffix,value,ev,stage=None,money=False):
        i,f=target(suffix,stage)
        matches=[d for d in f['matches'] if '变电站' in d['applicability']]
        if f['matches'] and not matches:
            issues.append(f['column']+'：OWL 适用工程类型不符，未填写'); return
        if matches and money and any(d['standardUnit'] not in ('元','万元') for d in matches):
            issues.append(f['column']+'：OWL 单位与金额不符，未填写'); return
        if matches and stage and any(('初步设计' if '初步设计' in stage else '结算') not in d['applicability'] for d in matches):
            issues.append(f['column']+'：OWL 阶段不符，未填写'); return
        ev.update(route='OWL 约束' if matches else '模板字段', definitions=[d['id'] for d in matches],
                  templateField=f['label'],templateCell=f['column']+str(sheet['headerRows']+1),
                  unit='万元' if money else ev.get('unit',''),value=value)
        if money:
            ev['standardValue']=str(Decimal(ev['rawValue']) if ev['sourceUnit']=='元' else Decimal(str(value))*10000);ev['standardUnit']='元'
        values[i]=value;evidence[f['column']]=ev
    def xl(suffix,sh,cell,stage=None,money=False,transform=None,note=''):
        ws=book[sh];raw=ws[cell].value
        if raw is None or (isinstance(raw,str) and raw.startswith('#')): return
        val=transform(raw) if transform else raw
        if money: val=float((Decimal(str(raw))/10000).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP))
        if hasattr(val,'strftime'):val=val.strftime('%Y-%m-%d')
        ev={'file':str(sources[0]),'sha256':source_hash,'location':sh+'!'+cell,'rawValue':str(raw),
            'sourceUnit':'元' if money else '', 'method':'Excel 单元格读取（公式使用文件内缓存值）',
            'basis':note or (tax if money else '工程基础信息'), 'conversion':'元 ÷ 10000 → 万元，保留4位小数' if money else '按字段语义规范化'}
        put(suffix,val,ev,stage,money)
    def row_cell(sh,label,col):
        hits=[r[1].row for r in book[sh].iter_rows(max_col=2) if clean(r[1].value)==label]
        if len(hits)!=1:raise ValueError('来源行缺失或不唯一：'+sh+' / '+label)
        return col+str(hits[0])
    sh='单体封面'
    if '秀清220千伏变电站新建工程' not in clean(book[sh]['C7'].value):raise ValueError('工程对象不匹配')
    xl('工程名称',sh,'C7')
    project_code=str(book[sh]['C6'].value)
    if len(project_code)==14 and project_code.isdigit():xl('工程编码',sh,'C6')
    else:issues.append('工程编码：来源为ERP单体编号 '+project_code+'，不是模板要求的14位工程编码，未直接代填。')
    xl('所属公司',sh,'C8',transform=lambda v:'江苏' if '江苏省' in v else v)
    xl('所属区域',sh,'C8',transform=lambda v:'华东',note='来源省公司为江苏，按区域对应关系归入华东。')
    xl('所属地区','01-2变电(换流)竣工工程概况表','B5',transform=lambda v:v.split('市')[0])
    xl('竣工时间','01-2变电(换流)竣工工程概况表','J11')
    xl('高压侧（kV）',sh,'C7',transform=lambda v:int(re.search(r'(\d+)千伏',v).group(1)))
    xl('建设性质',sh,'C7',transform=lambda v:'新建变电站')
    stage='竣工决算（结算）（二级、三级指标）';sh='02竣工工程决算一览表'
    assert clean(book[sh]['K5'].value)=='安装工程' and clean(book[sh]['I4'].value)=='实际价值'
    for field,label,col in [('建筑费合计','工程静态投资','I'),('安装工程费','工程静态投资','K'),
        ('设备费合计','工程静态投资','L'),('其他费用合计','其他费用','M'),
        ('静态投资','工程静态投资','N'),('动态投资','项目总投资','N'),('增值税抵扣税额','项目总投资','O'),
        ('场地平整费用（万元）','场地平整','I'),
        ('继电保护','继电保护','L'),('智能辅助控制系统','智能辅助控制系统','L'),('在线监测系统','在线监测系统','L')]:
        xl(field,sh,row_cell(sh,label,col),stage,True)
    other='03其他费用明细表'
    for field,label in [('建场费合计','建设场地征用及清理费'),('项目建设管理费 / 合计','项目建设管理费'),
        ('其中：工程监理费','工程监理费'),('项目建设技术服务费 / 合计','项目建设技术服务费'),
        ('其中：项目前期工作费','项目前期工作费'),('其中：工程建设检测费','工程建设检测费')]:
        xl(field,other,row_cell(other,label,'J'),stage,True)
    # The source records the combined survey/design amount, not a usable split.
    issues.append('勘察费、设计费：来源合并计列勘察设计费，子行虽为0但不代表实际没有费用；不拆分填0。')
    pdf_used=[]
    if len(pdfs)==1:
        p=pdfs[0];ph=digest(p)
        with pdfplumber.open(p) as pdf:
            page=pdf.pages[33];text=clean(PdfReader(p).pages[33].extract_text())
            if '秀清' not in text or '总概算表' not in text or '万元' not in text:raise ValueError('初设PDF第34页表题/单位校验失败')
            tables=page.extract_tables()
            table=next(t for t in tables if t and '安装' in clean(t[0][4]))
            def pdfval(rowlabel,col):
                found=[(n,r) for n,r in enumerate(table,1) if re.search('.*?'.join(map(re.escape,rowlabel)),clean(r[1]))]
                if len(found)!=1:raise ValueError('PDF行不唯一：'+rowlabel)
                n,row=found[0];raw=clean(row[col]);nums=re.findall(r'(?<![\d.-])\d+(?:\.\d+)?(?![\d.-])',raw)
                if len(nums)!=1:raise ValueError('PDF数值受水印干扰，无法唯一确认：'+raw)
                return float(nums[0]),{'file':str(p),'sha256':ph,'location':f'第34页 / 表格第{n}行第{col+1}列',
                   'rawValue':row[col],'sourceUnit':'万元','method':'PDF 原生表格解析 + 行列定位',
                   'basis':'初步设计批复概算；仅取秀清变电站表，工程静态投资行包含编制期价差，不取小计。',
                   'quote':rowlabel+' / '+clean(table[0][col]),'conversion':'原文万元直接回填'}
            initial='初步设计批复概算(万元)'
            for field,label,col in [('建筑','工程静态投资',2),('设备','工程静态投资',3),('安装','工程静态投资',4),
                ('其他费用合计','其他费用',5),('建场费合计','建设场地征用及清理费',5),('基本预备费','基本预备费',5),
                ('静态投资','工程静态投资',6),('贷款利息','建设期贷款利息',5),('动态投资','工程动态投资',6)]:
                v,ev=pdfval(label,col);put(field,v,ev,initial,True)
            pdf_used=[str(p)]
    else: issues.append('初设批复PDF缺失或存在多个版本，未自动选取。')
    book.close()
    for f in sheet['fields']:
        f['evidence']=evidence.get(f['column'])
        f['missingReason']='本轮未取得可回填证据；不代表全部资料中不存在。'
    sheet['rows']=[values];info['activeSheet']=sheet['name']
    info['extraction']={'mode':'真实资料抽取','method':'程序读取 Excel / PDF，OWL 约束与模板字段双路径回填；本轮未新增大模型推理。',
      'sources':[str(sources[0])]+pdf_used,'filled':len(evidence),'owlCount':sum(e['route']=='OWL 约束' for e in evidence.values()),
      'templateCount':sum(e['route']=='模板字段' for e in evidence.values()),'missing':values.count('未包含'),'issues':issues,
      'scope':'本轮覆盖审定决算 Excel 与初设批复 PDF；其他文件尚未全量抽取，.zwzj 按要求跳过。',
      'taxBasis':tax}
    from supplement import enrich
    return enrich(info)
