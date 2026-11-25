import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const data=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
const wb=Workbook.create();
const col=n=>{let v='';for(;n;n=Math.floor((n-1)/26))v=String.fromCharCode(65+(n-1)%26)+v;return v;};
for(const s of data.sheets){
 const sh=wb.worksheets.add(s.name),last=col(s.columns);
 sh.getRange(`A1:${last}${s.headerRows+Math.max(s.rows.length,1)}`).format={font:{name:'Microsoft YaHei',size:10,color:'#263B38'},rowHeight:30,verticalAlignment:'center',wrapText:true};
 for(const c of s.cells){const range=sh.getRange(c.address);range.values=[[c.value]];range.format={fill:c.fill||'#E7F0EC',font:{name:'Microsoft YaHei',size:c.fontSize,bold:c.bold},horizontalAlignment:'center'};}
 for(const m of s.merges)sh.getRange(m.range).merge();
 s.widths.forEach((w,i)=>sh.getRange(`${col(i+1)}1:${col(i+1)}${s.headerRows+Math.max(s.rows.length,1)}`).format.columnWidthPx=w);
 if(s.rows.length){sh.getRange(`A${s.headerRows+1}:${last}${s.headerRows+s.rows.length}`).values=s.rows;sh.getRange(`A${s.headerRows+1}:${last}${s.headerRows+s.rows.length}`).format.rowHeight=58;}
 sh.freezePanes.freezeRows(s.headerRows);sh.freezePanes.freezeColumns(1);
}
if(data.extraction){
 const sh=wb.worksheets.add('取值依据');
 const headers=['模板单元格 / 工程','字段路径','填入值','模板单位','抽取依据','源文件','来源位置','原始值','原始单位','换算','业务口径','解析方式','源文件SHA256'];
 const rows=data.sheets.flatMap(s=>(s.rowFields||[s.fields]).flatMap((fields,ri)=>fields.filter(f=>f.evidence).map(f=>{const e=f.evidence;return [e.templateCell+' / '+(s.rowProjects?.[ri]||''),e.templateField,e.value,e.unit,e.route,e.file,e.location,e.rawValue,e.sourceUnit,e.conversion,e.basis,e.method,e.sha256]})));
 sh.getRange('A1:M1').merge();sh.getRange('A1').values=[[data.extraction.scope+' 未包含不等于源资料不存在。']];
 sh.getRange('A2:M2').values=[headers];if(rows.length)sh.getRange(`A3:M${rows.length+2}`).values=rows;
 sh.getRange(`A1:M${rows.length+2}`).format={font:{name:'Microsoft YaHei',size:10},wrapText:true,rowHeight:66,columnWidthPx:180,verticalAlignment:'center'};
 sh.getRange('A1:M2').format.fill='#E7F0EC';sh.getRange('A1:M2').format.font.bold=true;
 sh.getRange(`B1:B${rows.length+2}`).format.columnWidthPx=340;
 sh.getRange(`F1:F${rows.length+2}`).format.columnWidthPx=380;
 sh.freezePanes.freezeRows(2);
 const gaps=wb.worksheets.add('未填与冲突');
 const gapRows=data.sheets.flatMap(s=>(s.rowFields||[s.fields]).flatMap((fields,ri)=>fields.filter(f=>f.column!=='A').flatMap(f=>f.evidence?(f.conflicts||[]).map(c=>[c.templateCell+' / '+(s.rowProjects?.[ri]||''),f.label,'来源冲突',String(c.retainedValue),String(c.value),c.reason,c.file+' / '+c.location]):[[f.column+(s.headerRows+ri+1)+' / '+(s.rowProjects?.[ri]||''),f.label,f.missingStatus||'证据不足','未包含','',f.missingReason,'']])));
 gaps.getRange('A1:G1').values=[['模板位置','字段路径','状态','模板保留值','其他来源值','原因 / 处理','其他证据来源']];
 if(gapRows.length)gaps.getRange(`A2:G${gapRows.length+1}`).values=gapRows;
 gaps.getRange(`A1:G${gapRows.length+1}`).format={font:{name:'Microsoft YaHei',size:10},wrapText:true,rowHeight:100,columnWidthPx:130,verticalAlignment:'center'};
 gaps.getRange(`B1:B${gapRows.length+1}`).format.columnWidthPx=390;
 gaps.getRange(`F1:G${gapRows.length+1}`).format.columnWidthPx=390;
 gaps.getRange('A1:G1').format.fill='#E7F0EC';gaps.getRange('A1:G1').format.font.bold=true;
 gaps.freezePanes.freezeRows(1);
}
wb.recalculate();
await(await SpreadsheetFile.exportXlsx(wb)).save(process.argv[3]);
console.log('exported');
