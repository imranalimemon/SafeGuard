from pathlib import Path
import fitz,json,sys
p=Path(sys.argv[1])
doc=fitz.open(p)
text='\n'.join(page.get_text() for page in doc)
for index,name in [(0,'pdf-title.png'),(1,'pdf-summary.png')]:
 doc[index].get_pixmap(matrix=fitz.Matrix(1,1)).save(str(p.parent/name))
result={'command':'python -B tools/inspect_pdf.py '+str(p),'pages':len(doc),'bytes':p.stat().st_size,'opens':True,'title_page':'SafeGuard PPE violation report' in doc[0].get_text(),'summary_chart_page':'Summary of filtered records' in doc[1].get_text(),'filtered_table':'Filtered incident table' in text,'evidence_thumbnails':'Evidence thumbnails' in text}
(p.parent/'pdf-inspection.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
