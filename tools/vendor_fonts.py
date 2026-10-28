"""Fetch the existing Google font assets/licenses for local offline serving."""
from pathlib import Path
import hashlib,json,re,urllib.request
root=Path('frontend/public/fonts');root.mkdir(parents=True,exist_ok=True)
url='https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap'
css=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40).read().decode()
assets=[]
for source in sorted(set(re.findall(r'https://fonts.gstatic.com/[^)\s]+',css))):
 data=urllib.request.urlopen(source,timeout=40).read();name=hashlib.sha256(data).hexdigest()[:20]+Path(source).suffix
 (root/name).write_bytes(data);css=css.replace(source,'/fonts/'+name);assets.append({'source':source,'file':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(root/'fonts.css').write_text(css,encoding='utf-8')
licenses={name:'https://raw.githubusercontent.com/google/fonts/main/ofl/'+name+'/OFL.txt' for name in ['hankengrotesk','inter','jetbrainsmono']}
licenses['material-design-icons']='https://raw.githubusercontent.com/google/material-design-icons/master/LICENSE'
for name,source in licenses.items():(root/(name+'-LICENSE.txt')).write_bytes(urllib.request.urlopen(source,timeout=40).read())
(root/'sources.json').write_text(json.dumps({'css_source':url,'assets':assets,'licenses':licenses},indent=2))
p=Path('frontend/index.html');text=p.read_text(encoding='utf-8');text=re.sub(r'    <link[^\n]+https://fonts\.[^\n]+\n','',text);text=text.replace('    <title>','    <link rel="stylesheet" href="/fonts/fonts.css">\n    <title>');p.write_text(text,encoding='utf-8')
print('Saved',len(assets),'font assets and four license files.')
