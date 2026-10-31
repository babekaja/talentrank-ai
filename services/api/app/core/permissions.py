"""Permission checks are always enforced on the server, never only in Angular."""
from fastapi import Depends, HTTPException
from app.core.security import Principal, get_current_principal

CAN_WRITE = {'org_admin', 'recruiter'}
CAN_VIEW = {'org_admin', 'recruiter', 'evaluator'}


def require_role(*roles: str):
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(403, 'Permissions insuffisantes')
        return principal
    return dependency
