"""HTTP client to the private ML sidecar; never logs candidate text."""
import httpx
from app.core.config import get_settings

def ml_request(endpoint: str, payload: dict):
    cfg=get_settings()
    if not cfg.semantic_enabled:
        raise RuntimeError('SEMANTIC_DISABLED')
    if cfg.ml_service_token.startswith('CHANGE_'):
        raise RuntimeError('ML_TOKEN_NOT_CONFIGURED')
    with httpx.Client(timeout=180) as client:
        result=client.post(cfg.ml_service_url.rstrip('/')+endpoint,
                           json=payload,headers={'X-Internal-Token':cfg.ml_service_token})
        result.raise_for_status()
        return result.json()
