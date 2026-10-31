"""Limited HTML nesting check on 3 Angular inline templates; not Angular compilation."""
from html.parser import HTMLParser
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / 'apps/web/src/app/features'
FILES = ('insights/document-viewer.ts', 'matching/matching-detail.ts', 'matching/matching-compare.ts')
VOID = {'input','img','br','hr','meta','link','source','area','base','col','embed','wbr'}

class Checker(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.issues=[]
    def handle_starttag(self, tag, attrs):
        if tag not in VOID: self.stack.append(tag)
    def handle_endtag(self, tag):
        if not self.stack: self.issues.append(f'unexpected </{tag}>')
        elif self.stack[-1]!=tag: self.issues.append(f'expected </{self.stack[-1]}>, found </{tag}>')
        else: self.stack.pop()

issues=[]
for file in FILES:
    text=(ROOT/file).read_text()
    offset=text.index('template:`')+len('template:`')
    template=text[offset:text.index('`})', offset)]
    checker=Checker();checker.feed(template)
    if checker.issues or checker.stack:issues.append((file,checker.issues,checker.stack))
print({'checked_templates':len(FILES),'html_nesting_issues':len(issues),'angular_build_verified':False})
for issue in issues:print(issue)
sys.exit(bool(issues))
