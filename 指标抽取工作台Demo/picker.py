import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
sys.stdout.reconfigure(encoding='utf8')
root=tk.Tk();root.withdraw();root.attributes('-topmost',True)
kind=sys.argv[1]
current=Path(sys.argv[2]) if len(sys.argv)>2 and sys.argv[2] else None
directory=current if current and current.is_dir() else current.parent if current else Path.home()
if kind=='folder':directory=Path(__file__).resolve().parent.parent/'造价数据'
if not directory.is_dir():directory=Path.home()
root.update()
if kind=='folder': selected=filedialog.askdirectory(parent=root,title='选择工程资料文件夹',initialdir=str(directory),mustexist=True)
else: selected=filedialog.askopenfilename(parent=root,title='选择 Excel 模板' if kind=='template' else '选择 OWL 指标文件',initialdir=str(directory),filetypes=[('Excel 模板','*.xlsx')] if kind=='template' else [('OWL / RDF XML','*.owl *.rdf *.xml')])
root.destroy()
print(selected or '')
