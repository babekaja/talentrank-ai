import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { AuthService } from './auth.service';

describe('Session privée', () => {
  let service:AuthService;
  let http:HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({providers: [provideHttpClient(),provideHttpClientTesting()]});
    service=TestBed.inject(AuthService);
    http=TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());
  it('conserve le jeton uniquement en mémoire puis charge le rôle depuis le serveur', async () => {
    const pending=service.login({organization_slug:'demo',email:'demo@example.org',password:'test',remember_me:true});
    const login=http.expectOne('/api/v1/auth/login');
    expect(login.request.withCredentials).toBe(true);
    expect(login.request.body.remember_me).toBe(true);
    login.flush({access_token:'short-lived-token',token_type:'bearer',expires_in:900});
    await Promise.resolve();
    const me=http.expectOne('/api/v1/auth/me');
    me.flush({id:'1',full_name:'Test',email:'demo@example.org',organization_id:'org',
      organization_name:'Démo',organization_slug:'demo',role:'recruiter'});
    await pending;
    expect(service.token()).toBe('short-lived-token');
    expect(service.user()?.role).toBe('recruiter');
  });
  it('termine l initialisation sans session si le cookie est invalide', async () => {
    const pending=service.initialize();
    http.expectOne('/api/v1/auth/refresh').flush({}, {status:401,statusText:'Unauthorized'});
    await pending;
    expect(service.ready()).toBe(true);
    expect(service.user()).toBeNull();
    expect(service.token()).toBeNull();
  });
  it('crée le compte puis charge son organisation depuis le serveur', async () => {
    const pending=service.register({full_name:'Camille Test',organization_name:'Organisation de test',
      organization_slug:'test',email:'camille@example.org',password:'un-mot-de-passe-de-test'});
    const registration=http.expectOne('/api/v1/auth/register');
    expect(registration.request.withCredentials).toBe(true);
    expect(registration.request.body.role).toBeUndefined();
    expect(registration.request.body.password_confirmation).toBeUndefined();
    registration.flush({access_token:'registration-token',token_type:'bearer',expires_in:900});
    await Promise.resolve();
    http.expectOne('/api/v1/auth/me').flush({id:'2',full_name:'Camille Test',email:'camille@example.org',
      organization_id:'new-org',organization_name:'Organisation de test',organization_slug:'test',role:'org_admin'});
    await pending;
    expect(service.token()).toBe('registration-token');
    expect(service.user()?.organization_id).toBe('new-org');
    expect(service.user()?.role).toBe('org_admin');
  });
  it('reste sans session si la création est refusée', async () => {
    const pending=service.register({full_name:'Camille Test',organization_name:'Organisation de test',
      organization_slug:'test',email:'camille@example.org',password:'un-mot-de-passe-de-test'});
    const rejected=expect(pending).rejects.toMatchObject({status:409});
    http.expectOne('/api/v1/auth/register').flush({}, {status:409,statusText:'Conflict'});
    await rejected;
    expect(service.token()).toBeNull();
    expect(service.user()).toBeNull();
  });
  it('ouvre la démonstration sans envoyer d’identifiants et charge son périmètre serveur', async () => {
    const pending=service.enterDemo();
    const entry=http.expectOne('/api/v1/auth/demo');
    expect(entry.request.body).toEqual({});
    expect(entry.request.withCredentials).toBe(true);
    entry.flush({access_token:'demo-session-token',token_type:'bearer',expires_in:900});
    await Promise.resolve();
    http.expectOne('/api/v1/auth/me').flush({id:'demo',full_name:'Administrateur Démo',email:'demo@example.org',
      organization_id:'demo-org',organization_name:'Babetech',organization_slug:'babetech',role:'org_admin',demo_mode:true,demo_read_only:true});
    await pending;
    expect(service.token()).toBe('demo-session-token');
    expect(service.user()?.demo_mode).toBe(true);
    expect(service.user()?.organization_slug).toBe('babetech');
  });
});
