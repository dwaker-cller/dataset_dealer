"""File-level stage hints from relative directory names, then filename.

These hints are navigation metadata, not the business stage of extracted values.
"""
import re

STAGES=['前期与可研','初步设计','招标与合同','施工图与预算','施工与变更','竣工与验收','结算与审核','决算与审计','待归类']
PATTERNS={
 '前期与可研':r'可研|可行性研究|核准|立项|项目前期',
 '初步设计':r'初设|初步设计',
 '招标与合同':r'招标|投标|中标|合同|招标限价',
 '施工图与预算':r'施工图|全口径预算|施工预算',
 '施工与变更':r'变更|签证|施工记录|施工日志',
 '竣工与验收':r'开竣工|开工报告|竣工报告|竣工证明|验收|竣工图|竣工资料',
 '结算与审核':r'结算|一审报告|二审报告',
 '决算与审计':r'决算|财务审计',
}

def classify_stage(path):
    parts=re.split(r'[\\/]+',str(path))
    # Prefer the closest meaningful directory, rather than interpreting a report
    # title mentioning other stages as the stage of the whole file.
    for text in list(reversed(parts[:-1]))+[parts[-1]]:
        matches=[name for name,pattern in PATTERNS.items() if re.search(pattern,text)]
        if len(matches)==1:return {'stage':matches[0],'stageBasis':'目录/文件名：'+text}
        if len(matches)>1:return {'stage':'待归类','stageBasis':'名称涉及多个阶段：'+text}
    return {'stage':'待归类','stageBasis':'目录及文件名未提供明确工程阶段'}
