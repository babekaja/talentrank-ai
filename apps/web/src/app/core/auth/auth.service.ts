import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { DemoStatus, LoginPayload, Me, RegisterPayload, TokenResponse } from '../../shared/models/auth';

/** Access tokens stay in memory; refresh token is an HttpOnly cookie provided by the API. */
@Injectable({providedIn:'root'})
export class AuthService {
  private readonly http=inject(HttpClient);
  private readonly access=signal<string|null>(null);
  private refreshing:Promise<string|null>|null=null;
  readonly user=signal<Me|null>(null);
  readonly ready=signal(false);
  token(){return this.access();}

  /** Deduplicated refresh: concurrent 401 responses trigger only one cookie refresh. */
  refreshAccess():Promise<string|null>{
    if(!this.refreshing){
      this.refreshing=(async()=>{
        try {
          const response=await firstValueFrom(this.http.post<TokenResponse>('/api/v1/auth/refresh',{}, {withCredentials:true}));
          this.access.set(response.access_token);
          return response.access_token;
        }catch{this.clear();return null;}
      })().finally(()=>{this.refreshing=null;});
    }
    return this.refreshing;
  }

  async initialize():Promise<void>{
    try {
      const token=await this.refreshAccess();
      if(!token)return;
      this.user.set(await firstValueFrom(this.http.get<Me>('/api/v1/auth/me')));
    }catch{this.clear();}
    finally{this.ready.set(true);}
  }

  async login(payload:LoginPayload):Promise<void>{
    this.clear();
    const tokens=await firstValueFrom(this.http.post<TokenResponse>('/api/v1/auth/login',payload,{withCredentials:true}));
    await this.acceptTokens(tokens);
  }

  demoStatus():Promise<DemoStatus>{
    return firstValueFrom(this.http.get<DemoStatus>('/api/v1/auth/demo/status'));
  }

  async enterDemo():Promise<void>{
    this.clear();
    const tokens=await firstValueFrom(this.http.post<TokenResponse>('/api/v1/auth/demo',{}, {withCredentials:true}));
    await this.acceptTokens(tokens);
  }

  async register(payload:RegisterPayload):Promise<void>{
    this.clear();
    const tokens=await firstValueFrom(this.http.post<TokenResponse>('/api/v1/auth/register',payload,{withCredentials:true}));
    await this.acceptTokens(tokens);
  }

  private async acceptTokens(tokens:TokenResponse):Promise<void>{
    this.access.set(tokens.access_token);
    try{this.user.set(await firstValueFrom(this.http.get<Me>('/api/v1/auth/me')));}
    catch(error){this.clear();throw error;}
  }

  async logout():Promise<void>{
    try{await firstValueFrom(this.http.post('/api/v1/auth/logout',{}, {withCredentials:true}));}
    finally{this.clear();}
  }
  private clear(){this.access.set(null);this.user.set(null);}
}
