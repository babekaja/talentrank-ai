"""Offline audit of the user-supplied responsive decorative pack and its Angular usages."""
from pathlib import Path
import json,re,sys
from PIL import Image
BASE=Path(__file__).resolve().parents[1]
ASSETS=BASE/'apps/web/public/assets/talentrank'
APP=BASE/'apps/web/src/app'
items=json.loads((BASE/'docs/illustrations-v22.json').read_text(encoding='utf-8'))
source='\n'.join(p.read_text(encoding='utf-8') for p in APP.rglob('*.ts'))
checks=[]; errors=[]
for item in items:
  name=item['name']
  for width in (480,960):
    p=ASSETS/f'{name}-{width}.webp'
    if not p.is_file(): errors.append(f'Missing {p}');continue
    with Image.open(p) as image:
      if image.format!='WEBP' or image.width!=width or image.mode!='RGBA':
        errors.append(f'Invalid variant: {p}, {image.mode}, {image.size}')
      if image.getextrema()[-1][0]!=0: errors.append(f'No transparent pixels in {p}')
      if image.height==0: errors.append(f'Invalid height: {p}')
    if p.stat().st_size > 200*1024: errors.append(f'Large variant: {p}')
    checks.append(p.name)
  active=item['status']=='active'
  used=bool(re.search(r'(?:name|art|illustration)="'+re.escape(name)+'"',source))
  if active != used: errors.append(f'Status/use mismatch {name}: active={active}, used={used}')
if len(items)!=20 or len(set(x['name'] for x in items))!=20: errors.append('Manifest count mismatch')
if 'loading="lazy"' not in source and "'lazy'" not in source: errors.append('Lazy loading missing')
if '<img' not in (APP/'shared/ui/tr-illustration.ts').read_text():errors.append('No img renderer')
if errors:
  print(json.dumps({'ok':False,'errors':errors},ensure_ascii=False,indent=2));sys.exit(1)
print(json.dumps({'ok':True,'illustrations':len(items),'webp_variants':len(checks),'active':sum(x['status']=='active' for x in items),'reserved':sum(x['status']=='reserved' for x in items),'description':'Static integration checks, NOT an Angular build.'},ensure_ascii=False,indent=2))
