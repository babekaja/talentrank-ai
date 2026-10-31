"""Playwright smoke on a REAL running Angular build; no mocked UI responses.

Use ONLY with an isolated fictional test organization. Requires `pip install playwright`
and `python -m playwright install chromium`. No screenshots of private CVs.
"""
from __future__ import annotations
import os, sys
from playwright.sync_api import sync_playwright


def main():
    needed=['TR_SMOKE_URL','TR_SMOKE_ORG','TR_SMOKE_EMAIL','TR_SMOKE_PASSWORD']
    absent=[n for n in needed if not os.environ.get(n)]
    if absent: raise SystemExit('Missing synthetic-test variables: '+', '.join(absent))
    base=os.environ['TR_SMOKE_URL'].rstrip('/')
    if not (base.startswith('http://127.0.0.1:') or base.startswith('http://localhost:')
            or base.startswith('https://')):
        raise SystemExit('Browser URL must use HTTPS or localhost')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            for size in [{'width':1366,'height':900},{'width':390,'height':844}]:
                page=browser.new_page(viewport=size)
                page.goto(base+'/connexion',wait_until='domcontentloaded',timeout=40000)
                page.get_by_label('Code de votre entreprise').fill(os.environ['TR_SMOKE_ORG'])
                page.get_by_label('Adresse email').fill(os.environ['TR_SMOKE_EMAIL'])
                page.get_by_label('Mot de passe',exact=True).fill(os.environ['TR_SMOKE_PASSWORD'])
                page.get_by_role('button',name='Se connecter').click()
                page.wait_for_url(lambda url: url.path not in ('/connexion','/'),timeout=40000)
                if page.get_by_role('alert').count():
                    raise AssertionError('Authentication resulted in a visible error')
                if page.locator('body').evaluate('(b)=>b.scrollWidth > innerWidth+4'):
                    raise AssertionError('Unexpected horizontal scrolling in viewport')
                print('PASS real browser login and layout:',size['width'],'px')
                page.close()
        finally:browser.close()

if __name__=='__main__':main()
