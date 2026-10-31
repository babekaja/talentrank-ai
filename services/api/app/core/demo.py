"""Périmètre serveur des sessions publiques de démonstration."""
import re

from fastapi import HTTPException, Request

from app.core.config import get_settings


def guard_demo_request(request: Request) -> None:
    path = request.url.path.rstrip('/')
    method = request.method.upper()
    if method in ('GET', 'HEAD', 'OPTIONS'):
        return
    # Le mode complet conserve les contrôles habituels du rôle et de l'organisation.
    if get_settings().demo_allow_writes:
        return
    if method == 'POST' and (re.fullmatch(r'/api/v1/matching-runs/[^/]+/compare', path)
                            or path in ('/api/v1/semantic/search', '/api/v1/skills/semantic-suggestions',
                                        '/api/v1/fairrank/identity-check')):
        return
    raise HTTPException(403, detail={
        'code': 'DEMO_RESTRICTED',
        'message': 'Cette action nécessite une connexion avec vos propres identifiants.',
    })
