"""Limited structural check of Angular inline template HTML; NOT Angular template parsing."""
from html.parser import HTMLParser
from pathlib import Path
import sys

VOID = {'input', 'img', 'br', 'hr', 'meta', 'link', 'source', 'area', 'base', 'col', 'embed', 'wbr'}
BASE = Path(__file__).resolve().parents[1] / 'apps/web/src/app/features'
SCREENS = (
    'shell/shell', 'dashboard/dashboard', 'candidates/candidates', 'uploads/uploads',
    'matching/matching', 'reviews/my-reviews', 'reviews/assignments',
    'training/training', 'jobs/jobs', 'campaigns/campaigns',
    'applications/applications', 'login/login', 'ml/ml-lab',
)
class Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []
    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)
    def handle_startendtag(self, tag, attrs):
        pass
    def handle_endtag(self, tag):
        if not self.stack:
            self.errors.append(f'unexpected closing tag {tag}')
        elif self.stack[-1] != tag:
            self.errors.append(f'expected </{self.stack[-1]}> but found </{tag}>')
        else:
            self.stack.pop()

def main():
    problems = []
    for screen in SCREENS:
        source = (BASE / f'{screen}.ts').read_text()
        begin = source.index('`', source.index('template:')) + 1
        end = source.index('`', begin)
        check = Checker()
        check.feed(source[begin:end])
        if check.errors or check.stack:
            problems.append(f'{screen}: {check.errors} {check.stack}')
    print({'templates_scanned': len(SCREENS), 'html_structure_issues': len(problems),
           'angular_template_compilation_verified': False})
    for p in problems:
        print(p)
    return int(bool(problems))

if __name__ == '__main__':
    sys.exit(main())
