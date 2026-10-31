import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { LucideArrowRight, LucideEye, LucideEyeOff, LucideLayers3 } from '@lucide/angular';
import { AuthService } from '../../core/auth/auth.service';
import { DemoStatus } from '../../shared/models/auth';

const LOGIN_HINT_KEY='talentrank.login-hint.v1';
type LoginHint={organization_slug:string;email:string};

function readLoginHint():LoginHint|null{
  try{
    const value=JSON.parse(localStorage.getItem(LOGIN_HINT_KEY)??'null');
    return value && typeof value.organization_slug==='string' && typeof value.email==='string' ? value : null;
  }catch{return null;}
}

function saveLoginHint(organization_slug:string,email:string):void{
  try{localStorage.setItem(LOGIN_HINT_KEY,JSON.stringify({organization_slug,email}));}catch{/* Storage may be blocked. */}
}

function forgetLoginHint():void{
  try{localStorage.removeItem(LOGIN_HINT_KEY);}catch{/* Storage may be blocked. */}
}

@Component({
  selector: 'tr-login', standalone: true,
  imports: [ReactiveFormsModule, RouterLink, LucideArrowRight, LucideEye, LucideEyeOff, LucideLayers3],
  template: `
  <main class="login-page min-h-screen grid lg:grid-cols-2">
    <section class="login-story relative hidden lg:flex flex-col justify-between overflow-hidden p-14 text-white" aria-label="Présentation de TalentRank AI">
      <div class="relative flex items-center gap-3"><div class="login-story__mark rounded-xl p-3"><svg lucideLayers3 [size]="27" /></div><strong class="text-2xl tracking-tight">TalentRank <span class="text-[#a5dce5]">AI</span></strong></div>
      <div class="relative max-w-lg space-y-6"><p class="login-story__eyebrow text-xs font-semibold uppercase tracking-[.12em]">Suivi des recrutements</p><h2 class="text-4xl font-bold leading-[1.15] tracking-tight">Chaque candidature au bon endroit.</h2><p class="text-lg leading-8 text-slate-200">Consultez les CV et les critères du poste, répartissez les dossiers à examiner et retrouvez les avis de votre équipe.</p></div>
      <p class="relative max-w-md border-t border-white/20 pt-5 text-sm leading-relaxed text-slate-300">Les résultats automatiques aident à lire les dossiers. La décision de recrutement appartient à votre équipe.</p>
    </section>
    <section class="login-form-panel flex min-h-screen items-center justify-center p-6 sm:p-12"><div class="w-full max-w-md">
      <div class="mb-10 flex items-center gap-3 lg:hidden"><svg lucideLayers3 class="text-[#245b93]" /><strong class="text-xl dark:text-white">TalentRank AI</strong></div>
      <div class="mb-9"><p class="login-form-panel__eyebrow mb-4 text-xs font-semibold uppercase tracking-[.1em]">Espace professionnel</p><h1 class="text-4xl font-bold tracking-tight text-slate-900 dark:text-white">Connexion à TalentRank AI</h1><p class="mt-3 text-slate-600 dark:text-slate-300">Saisissez le code de votre entreprise et vos identifiants.</p></div>
      @if(demo()?.enabled){<section class="soft-panel mb-7 p-4" aria-label="Démonstration du projet"><p class="text-sm font-semibold">Découvrir le projet avec {{demo()?.organization_name}}</p><p class="mt-1 text-sm muted">{{demo()?.read_only?'Consultez les CV, les classements et les rapports sans saisir d’identifiants.':'Ouvrez le compte de démonstration sans saisir d’identifiants.'}}</p><button type="button" class="btn-light mt-4 w-full justify-center !min-h-[50px]" [disabled]="pending() || demoPending()" (click)="startDemo()">{{demoPending()?'Ouverture de la démonstration…':'Tester le projet en mode démo'}} <svg lucideArrowRight [size]="18" aria-hidden="true"/></button>@if(demoError()){<p class="mt-3 text-sm text-red-700 dark:text-red-200" role="alert">{{demoError()}}</p>}</section>}
      <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-5" novalidate>
        <label class="block"><span class="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200">Code de votre entreprise</span><input formControlName="organization_slug" autocomplete="organization" placeholder="Exemple : kivu-tech" aria-describedby="company-code-help company-code-error" [attr.aria-invalid]="form.controls.organization_slug.touched && form.controls.organization_slug.invalid" class="login-field w-full rounded-xl px-4 py-3.5" /><small id="company-code-help" class="mt-1.5 block text-xs text-slate-600 dark:text-slate-300">Le code donné par votre organisation. Il se compose de lettres, chiffres et tirets.</small>@if(form.controls.organization_slug.touched && form.controls.organization_slug.invalid){<small id="company-code-error" class="mt-1 block text-sm text-red-700" role="alert">Saisissez le code de votre organisation avec des lettres minuscules, chiffres ou tirets.</small>}</label>
        <label class="block"><span class="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200">Adresse email</span><input formControlName="email" type="email" autocomplete="email" placeholder="vous@entreprise.com" [attr.aria-invalid]="form.controls.email.touched && form.controls.email.invalid" aria-describedby="login-email-error" class="login-field w-full rounded-xl px-4 py-3.5" />@if(form.controls.email.touched && form.controls.email.invalid){<small id="login-email-error" class="mt-1 block text-sm text-red-700" role="alert">Saisissez une adresse email valide.</small>}</label>
        <label class="block"><span class="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200">Mot de passe</span><span class="relative block"><input formControlName="password" [type]="showPassword() ? 'text' : 'password'" autocomplete="current-password" placeholder="Votre mot de passe" [attr.aria-invalid]="form.controls.password.touched && form.controls.password.invalid" aria-describedby="login-password-error" class="login-field w-full rounded-xl px-4 py-3.5 pr-14" /><button type="button" (click)="showPassword.set(!showPassword())" [attr.aria-label]="showPassword() ? 'Masquer le mot de passe' : 'Afficher le mot de passe'" [attr.aria-pressed]="showPassword()" class="login-password-toggle absolute right-1.5 top-1.5 text-slate-600 dark:text-slate-300">@if(showPassword()){<svg lucideEyeOff [size]="21" />}@else{<svg lucideEye [size]="21" />}</button></span>@if(form.controls.password.touched && form.controls.password.invalid){<small id="login-password-error" class="mt-1 block text-sm text-red-700" role="alert">Saisissez votre mot de passe.</small>}</label>
        <label class="login-remember flex cursor-pointer items-start gap-3 rounded-xl px-4 py-3.5 text-sm"><input formControlName="remember_me" type="checkbox" class="mt-0.5 h-4 w-4 rounded border-slate-300" /><span><strong class="block text-slate-800 dark:text-slate-100">Se souvenir de moi</strong><span class="mt-0.5 block text-xs text-slate-600 dark:text-slate-300">Rester connecté pendant 30 jours sur cet appareil.</span></span></label>
        @if(error()){<p role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{{error()}}</p>}
        <button type="submit" [disabled]="pending() || demoPending()" class="login-submit flex w-full items-center justify-center gap-2 rounded-xl px-4 py-4 font-semibold text-white transition disabled:opacity-50">{{pending()?'Connexion en cours…':'Se connecter'}} <svg lucideArrowRight [size]="18" /></button>
      </form>
      <p class="mt-7 text-center text-sm text-slate-600 dark:text-slate-300">Vous découvrez TalentRank AI ? <a routerLink="/inscription" class="font-semibold text-[#176b75] underline underline-offset-4 dark:text-[#a5dce5]">Créer un compte</a></p>
      <p class="mt-4 text-center text-xs leading-5 text-slate-500 dark:text-slate-400">Pour rejoindre une organisation existante, demandez une invitation à son administrateur.</p>
    </div></section>
  </main>`
})
export class Login implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly pending = signal(false);
  readonly error = signal('');
  readonly showPassword = signal(false);
  readonly demo=signal<DemoStatus|null>(null);
  readonly demoPending=signal(false);
  readonly demoError=signal('');
  private readonly hint=readLoginHint();
  readonly form = this.fb.nonNullable.group({
    organization_slug: [this.hint?.organization_slug??'', [Validators.required, Validators.pattern(/^[a-z0-9-]{2,80}$/)]],
    email: [this.hint?.email??'', [Validators.required, Validators.email]],
    password: ['', Validators.required],
    remember_me: [!!this.hint]
  });

  ngOnInit(){void this.loadDemo();}

  private async loadDemo(){
    try{this.demo.set(await this.auth.demoStatus());}
    catch{this.demo.set(null);}
  }

  async startDemo():Promise<void>{
    if(this.pending()||this.demoPending()||!this.demo()?.enabled)return;
    this.demoPending.set(true);this.demoError.set('');this.error.set('');
    try{
      await this.auth.enterDemo();
      await this.router.navigateByUrl('/tableau-de-bord',{replaceUrl:true});
    }catch(error){
      this.demoError.set(error instanceof HttpErrorResponse&&error.status===429
        ? 'Trop de demandes. Réessayez dans quelques instants.'
        : 'Impossible d’ouvrir la démonstration pour le moment. Réessayez.');
    }finally{this.demoPending.set(false);}
  }

  async submit(): Promise<void> {
    if (this.pending() || this.demoPending()) return;
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.pending.set(true); this.error.set('');
    try {
      const values=this.form.getRawValue();
      await this.auth.login(values);
      if(values.remember_me)saveLoginHint(values.organization_slug,values.email);
      else forgetLoginHint();
      await this.router.navigateByUrl('/');
    } catch (error) {
      this.error.set(error instanceof HttpErrorResponse && error.status === 401
        ? 'Email, mot de passe ou organisation incorrect.'
        : 'Impossible de se connecter. Vérifiez votre connexion et réessayez.');
    } finally {this.pending.set(false);}
  }
}
