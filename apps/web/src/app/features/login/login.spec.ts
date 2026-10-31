import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { Login } from './login';

describe('Bouton de démonstration sur la connexion', () => {
  let fixture:ComponentFixture<Login>;
  const auth={demoStatus:vi.fn(),enterDemo:vi.fn(),login:vi.fn()};
  let navigate:ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    vi.stubGlobal('localStorage',{getItem:vi.fn(()=>null),setItem:vi.fn(),removeItem:vi.fn()});
    auth.demoStatus.mockResolvedValue({enabled:true,organization_name:'Babetech',read_only:true});
    auth.enterDemo.mockResolvedValue(undefined);
    TestBed.configureTestingModule({imports:[Login],providers:[provideRouter([]),{provide:AuthService,useValue:auth}]});
    navigate=vi.spyOn(TestBed.inject(Router),'navigateByUrl').mockResolvedValue(true);
    fixture=TestBed.createComponent(Login);fixture.detectChanges();
    await fixture.whenStable();fixture.detectChanges();
  });
  afterEach(()=>{fixture?.destroy();vi.restoreAllMocks();vi.clearAllMocks();vi.unstubAllGlobals();});

  it('ouvre Babetech avec des champs de connexion vides', async () => {
    const button=Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>)
      .find(button=>button.textContent?.includes('Tester le projet en mode démo'))!;
    expect(button.type).toBe('button');expect(fixture.componentInstance.form.invalid).toBe(true);
    button.click();await fixture.whenStable();
    expect(auth.enterDemo).toHaveBeenCalledOnce();
    expect(auth.enterDemo).toHaveBeenCalledWith();
    expect(auth.login).not.toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith('/tableau-de-bord',{replaceUrl:true});
    expect(fixture.componentInstance.form.controls.password.value).toBe('');
  });

  it('bloque les doubles clics et permet de réessayer après une erreur', async () => {
    let reject!:(reason:Error)=>void;
    auth.enterDemo.mockReturnValueOnce(new Promise<void>((_,fail)=>{reject=fail;}));
    const pending=fixture.componentInstance.startDemo();
    await fixture.componentInstance.startDemo();
    await fixture.componentInstance.submit();
    expect(auth.enterDemo).toHaveBeenCalledOnce();expect(auth.login).not.toHaveBeenCalled();
    reject(new Error('Indisponible'));await pending;fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('Impossible d’ouvrir');
    expect(fixture.componentInstance.demoPending()).toBe(false);
    await fixture.componentInstance.startDemo();
    expect(auth.enterDemo).toHaveBeenCalledTimes(2);
    expect(navigate).toHaveBeenCalledOnce();
  });

  it('masque le bouton quand le serveur désactive la démonstration', () => {
    fixture.componentInstance.demo.set({enabled:false});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('Tester le projet en mode démo');
  });
});
