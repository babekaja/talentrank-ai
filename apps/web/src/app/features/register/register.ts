import { Component, ElementRef, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { AbstractControl, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { LucideArrowRight, LucideEye, LucideEyeOff, LucideLayers3 } from '@lucide/angular';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'tr-register', standalone: true,
  imports: [ReactiveFormsModule, RouterLink, LucideArrowRight, LucideEye, LucideEyeOff, LucideLayers3],
  template: `
  <main class="login-page min-h-screen grid lg:grid-cols-2">
    <section class="login-story relative hidden lg:flex flex-col justify-between overflow-hidden p-14 text-white" aria-label="Présentation de TalentRank AI">
      <a routerLink="/connexion" class="relative flex items-center gap-3"><div class="login-story__mark rounded-xl p-3"><svg lucideLayers3 [size]="27" /></div><strong class="text-2xl tracking-tight">TalentRank <span class="text-[#a5dce5]">AI</span></strong></a>
      <div class="relative max-w-lg space-y-6"><p class="login-story__eyebrow text-xs font-semibold uppercase tracking-[.12em]">Suivi des recrutements</p><h2 class="text-4xl font-bold leading-[1.15] tracking-tight">Votre espace pour examiner les candidatures.</h2><p class="text-lg leading-8 text-slate-200">Créez les postes à pourvoir, consultez les CV et partagez les dossiers avec votre équipe.</p></div>
      <p class="relative max-w-md border-t border-white/20 pt-5 text-sm leading-relaxed text-slate-300">Les résultats automatiques aident à lire les dossiers. La décision de recrutement appartient à votre équipe.</p>
    </section>
    <section class="login-form-panel flex min-h-screen items-center justify-center p-6 sm:p-12"><div class="w-full max-w-md">
      <a routerLink="/connexion" class="mb-8 flex items-center gap-3 lg:hidden"><svg lucideLayers3 class="text-[#245b93]" /><strong class="text-xl dark:text-white">TalentRank AI</strong></a>
      <div class="mb-7"><p class="login-form-panel__eyebrow mb-4 text-xs font-semibold uppercase tracking-[.1em]">Nouvel espace professionnel</p><h1 class="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Créer un compte</h1><p class="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">Créez votre espace pour examiner les candidatures. Vous en serez l’administrateur et pourrez inviter votre équipe.</p></div>
      <form [formGroup]="form" (ngSubmit)="submit()" [attr.aria-busy]="pending()" class="space-y-4" novalidate>
        <p class="text-xs text-slate-500 dark:text-slate-400">Tous les champs sont obligatoires.</p>
        <label class="block"><span id="register-name-label" class="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200">Nom complet</span><input formControlName="full_name" aria-labelledby="register-name-label" required autocomplete="name" maxlength="180" [attr.aria-invalid]="invalid('full_name')" aria-describedby="register-name-error" class="login-field w-full rounded-xl px-4 py-3" />@if(invalid('full_name')){<small id="register-name-error" class="mt-1 block text-sm text-red-700 dark:text-red-300" role="alert">Saisissez votre nom complet, de 2 à 180 caractères.</small>}</label>
        <label class="block"><span id="register-org-label" class="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200">Nom de votre organisation</span><input formControlName="organization_name" aria-labelledby="register-org-label" required autocomplete="organization" maxlength="180" [attr.aria-invalid]="invalid('organization_name')" aria-describedby="register-org-error" class="login-field w-full rounded-xl px-4 py-3" />@if(invalid('organization_name')){<small id="register-org-error" class="mt-1 block text-sm text-red-700 dark:text-red-300" role="alert">Saisissez un nom d’organisation, de 2 à 180 caractères.</small>}</label>
        <label class="block"><span id="register-code-label" class="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200">Code de votre organisation</span><input formControlName="organization_slug" aria-labelledby="register-code-label" required autocomplete="off" autocapitalize="none" spellcheck="false" maxlength="80" placeholder="Exemple : kivu-tech" [attr.aria-invalid]="invalid('organization_slug')" aria-describedby="register-code-help register-code-error" class="login-field w-full rounded-xl px-4 py-3" /><small id="register-code-help" class="mt-1.5 block text-xs leading-5 text-slate-600 dark:text-slate-300">Choisissez un code de 2 à 80 caractères : lettres minuscules, chiffres et tirets. Il servira à vous connecter.</small>@if(invalid('organization_slug')){<small id="register-code-error" class="mt-1 block text-sm text-red-700 dark:text-red-300" role="alert">Saisissez un code valide avec des lettres minuscules, chiffres ou tirets.</small>}</label>
        <label class="block"><span id="register-email-label" class="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200">Adresse email</span><input formControlName="email" aria-labelledby="register-email-label" required type="email" autocomplete="email" maxlength="254" [attr.aria-invalid]="invalid('email')" aria-describedby="register-email-error" class="login-field w-full rounded-xl px-4 py-3" />@if(invalid('email')){<small id="register-email-error" class="mt-1 block text-sm text-red-700 dark:text-red-300" role="alert">Saisissez une adresse email valide.</small>}</label>
        <label class="block"><span id="register-password-label" class="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200">Mot de passe</span><span class="relative block"><input formControlName="password" aria-labelledby="register-password-label" required [type]="showPassword() ? 'text' : 'password'" autocomplete="new-password" minlength="12" maxlength="256" [attr.aria-invalid]="invalid('password')" aria-describedby="register-password-help register-password-error" class="login-field w-full rounded-xl px-4 py-3 pr-14" /><button type="button" (click)="showPassword.set(!showPassword())" [attr.aria-label]="showPassword() ? 'Masquer le mot de passe' : 'Afficher le mot de passe'" [attr.aria-pressed]="showPassword()" class="login-password-toggle absolute right-1.5 top-1 text-slate-600 dark:text-slate-300">@if(showPassword()){<svg lucideEyeOff [size]="21" />}@else{<svg lucideEye [size]="21" />}</button></span><small id="register-password-help" class="mt-1.5 block text-xs text-slate-600 dark:text-slate-300">De 12 à 256 caractères.</small>@if(invalid('password')){<small id="register-password-error" class="mt-1 block text-sm text-red-700 dark:text-red-300" role="alert">Le mot de passe doit contenir de 12 à 256 caractères.</small>}</label>
        <label class="block"><span id="register-confirm-label" class="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200">Confirmer le mot de passe</span><input formControlName="password_confirmation" aria-labelledby="register-confirm-label" required [type]="showPassword() ? 'text' : 'password'" autocomplete="new-password" maxlength="256" [attr.aria-invalid]="confirmationInvalid()" aria-describedby="register-confirm-error" class="login-field w-full rounded-xl px-4 py-3" />@if(confirmationInvalid()){<small id="register-confirm-error" class="mt-1 block text-sm text-red-700 dark:text-red-300" role="alert">Les deux mots de passe doivent être identiques.</small>}</label>
        @if(error()){<p role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{{error()}}</p>}
        <button type="submit" [disabled]="pending()" class="login-submit flex w-full items-center justify-center gap-2 rounded-xl px-4 py-4 font-semibold text-white transition disabled:opacity-50">{{pending() ? 'Création en cours…' : 'Créer mon compte'}} <svg lucideArrowRight [size]="18" /></button>
      </form>
      <p class="mt-6 text-center text-sm text-slate-600 dark:text-slate-300">Vous avez déjà un compte ? <a routerLink="/connexion" class="font-semibold text-[#176b75] underline underline-offset-4 dark:text-[#a5dce5]">Se connecter</a></p>
      <p class="mt-4 text-center text-xs leading-5 text-slate-500 dark:text-slate-400">Pour rejoindre une organisation existante, utilisez le lien d’invitation envoyé par son administrateur.</p>
    </div></section>
  </main>`
})
export class Register {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly pending = signal(false);
  readonly error = signal('');
  readonly showPassword = signal(false);
  readonly form = this.fb.nonNullable.group({
    full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(180), Validators.pattern(/\S/)]],
    organization_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(180), Validators.pattern(/\S/)]],
    organization_slug: ['', [Validators.required, Validators.pattern(/^[a-z0-9-]{2,80}$/)]],
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    password: ['', [Validators.required, Validators.minLength(12), Validators.maxLength(256)]],
    password_confirmation: ['', Validators.required],
  }, {validators: (form: AbstractControl) => form.get('password')?.value === form.get('password_confirmation')?.value ? null : {passwordMismatch: true}});

  invalid(name: keyof typeof this.form.controls): boolean {
    const control = this.form.controls[name];
    return control.touched && control.invalid;
  }

  confirmationInvalid(): boolean {
    return this.form.controls.password_confirmation.touched &&
      (this.form.controls.password_confirmation.invalid || this.form.hasError('passwordMismatch'));
  }

  async submit(): Promise<void> {
    if (this.pending()) return;
    const values = this.form.getRawValue();
    this.form.patchValue({
      full_name: values.full_name.trim(), organization_name: values.organization_name.trim(),
      organization_slug: values.organization_slug.trim().toLowerCase(), email: values.email.trim().toLowerCase(),
    });
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      const field = this.host.nativeElement.querySelector<HTMLInputElement>('input.ng-invalid')
        ?? this.host.nativeElement.querySelector<HTMLInputElement>('[formControlName="password_confirmation"]');
      field?.focus();
      return;
    }
    this.pending.set(true);
    this.error.set('');
    try {
      const {password_confirmation, ...payload} = this.form.getRawValue();
      await this.auth.register(payload);
      this.form.controls.password.reset();
      this.form.controls.password_confirmation.reset();
      await this.router.navigateByUrl('/demarrer');
    } catch (error) {
      const status = error instanceof HttpErrorResponse ? error.status : 0;
      this.error.set(status === 409
        ? 'Création impossible avec cette adresse email ou ce code d’organisation. Connectez-vous si vous avez déjà un compte, ou choisissez un autre code.'
        : status === 429 ? 'Trop de tentatives. Patientez quelques minutes avant de réessayer.'
        : status === 422 ? 'Vérifiez les informations saisies et utilisez un mot de passe de 12 à 256 caractères.'
        : status === 503 ? 'La création de compte est indisponible pour le moment. Réessayez plus tard.'
        : 'Impossible de créer le compte. Vérifiez votre connexion et réessayez.');
    } finally { this.pending.set(false); }
  }
}
