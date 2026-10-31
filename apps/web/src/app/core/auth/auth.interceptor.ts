import { inject } from '@angular/core';
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

/** Refresh once after expiration; never retry credential endpoints or off-origin URLs. */
export const authInterceptor:HttpInterceptorFn=(request,next)=>{
  if(!request.url.startsWith('/api/') || request.url.startsWith('/api/v1/candidate-portal/'))return next(request);
  const auth=inject(AuthService);
  const token=auth.token();
  const authenticated=token ? request.clone({setHeaders:{Authorization:`Bearer ${token}`}}) : request;
  const credentialEndpoint=/^\/api\/v1\/auth\/(login|register|logout|refresh|demo)$/.test(request.url);
  return next(authenticated).pipe(catchError(error=>{
    if(!(error instanceof HttpErrorResponse) || error.status!==401 || credentialEndpoint || !token){return throwError(()=>error);}
    return from(auth.refreshAccess()).pipe(switchMap(newToken=>{
      if(!newToken)return throwError(()=>error);
      return next(request.clone({setHeaders:{Authorization:`Bearer ${newToken}`}}));
    }));
  }));
};
