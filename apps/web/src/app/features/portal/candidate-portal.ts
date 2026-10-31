import {Component, inject, signal} from '@angular/core';
import {HttpClient, HttpHeaders} from '@angular/common/http';
import {FormsModule} from '@angular/forms';
import {firstValueFrom} from 'rxjs';
import {TrIcon} from '../../shared/ui/tr-icon';
import {apiError} from '../../shared/recruitment';

interface Me {candidate_reference:string;training_consent:boolean;notice_version:string;notice:string}
interface Course {title:string;provider:string;official_url:string;language:string;level:string}
interface Suggestions {status:string;items:Course[];notice?:string}
@Component({selector:'tr-candidate-portal',standalone:true,imports:[FormsModule,TrIcon],template:`
<main class="min-h-screen bg-slate-50 dark:bg-slate-950 px-4 py-10">
 <div class="mx-auto max-w-2xl">
  <div class="flex items-center gap-2 text-indigo-700 font-bold"><tr-icon name="graduation-cap" [size]="24"/> TalentRank AI</div>
  <h1 class="mt-5 text-3xl font-bold">Mon espace candidat</h1>
  <p class="mt-3 text-slate-600 dark:text-slate-300">Vos compétences vous appartiennent. Choisissez librement si vous souhaitez consulter des pistes de formation.</p>
  @if(error()){<p role="alert" class="alert-error mt-5">{{error()}}</p>}
  @if(message()){<p role="status" class="alert-ok mt-5">{{message()}}</p>}
  @if(!me()){
    <section class="card mt-7 p-7">
     <h2 class="section-heading">Vérifier mon adresse email</h2>
     <p class="section-caption mt-2">Saisissez le code temporaire reçu par email. Aucun mot de passe et aucun résultat de recrutement ne sont envoyés dans le message.</p>
     <form (ngSubmit)="verify()" class="mt-6 space-y-4">
      <label class="block"><span class="field-label">Code de vérification</span>
       <input class="field" type="password" autocomplete="one-time-code" name="code" [(ngModel)]="code" minlength="40" required placeholder="Coller le code reçu"/></label>
      <button class="btn-primary" type="submit" [disabled]="busy()||code.trim().length<40">{{busy()?'Vérification…':'Accéder à mon espace'}}</button>
     </form>
     <p class="mt-4 text-sm text-slate-500">Pas reçu de code ? Contactez l'entreprise auprès de laquelle vous avez candidaté.</p>
    </section>
  } @else {
    <section class="card mt-7 p-7">
     <div class="flex justify-between gap-3"><h2 class="section-heading">Mes préférences</h2><button type="button" class="btn-light" (click)="logout()"><tr-icon name="log-out" [size]="16"/> Se déconnecter</button></div>
     <p class="mt-2 text-sm text-slate-500">Référence de dossier : {{me()?.candidate_reference}}</p>
     <p class="mt-5 text-sm leading-relaxed whitespace-pre-line">{{me()?.notice}}</p>
     <div class="mt-6 border rounded-xl p-4">
      <p class="font-semibold">Suggestions de formation facultatives</p>
      <p class="section-caption mt-1">Votre décision n'a aucune influence sur votre candidature.</p>
      <p class="mt-3 font-medium">{{me()?.training_consent?'Autorisé par vous':'Non autorisé'}}</p>
      <button type="button" class="btn-primary mt-4" [disabled]="busy()" (click)="setConsent(!me()!.training_consent)">
        {{me()?.training_consent?'Retirer mon accord':'J’accepte de recevoir des pistes de formation'}}
      </button>
     </div>
    </section>
    @if(me()?.training_consent){<section class="card mt-6 p-7"><div class="flex items-center justify-between gap-3"><h2 class="section-heading">Formations proposées</h2><button class="btn-light" type="button" (click)="loadSuggestions()" [disabled]="busy()"><tr-icon name="refresh-cw" [size]="16"/> Actualiser</button></div>
      @if(suggestions()?.items?.length){<div class="mt-5 grid gap-3">@for(c of suggestions()!.items;track c.official_url){<article class="soft-panel p-4"><h3 class="font-semibold">{{c.title}}</h3><p class="section-caption mt-1">{{c.provider}} · {{c.language}} · {{c.level}}</p><a class="inline-link mt-3 inline-block" [href]="c.official_url" rel="noopener noreferrer" target="_blank">Consulter la formation ↗</a></article>}</div>}
      @else{<p class="section-caption mt-4">Aucune formation vérifiée disponible pour votre dossier actuellement.</p>}
      <p class="section-caption mt-4">{{suggestions()?.notice}}</p>
     </section>}
  }
  <p class="mt-8 text-xs text-slate-500">Ce service ne prend aucune décision d'embauche. Le retrait de l'accord est possible à tout moment.</p>
 </div>
</main>
`})
export class CandidatePortal {
 private http=inject(HttpClient);
 readonly error=signal('');readonly message=signal('');readonly busy=signal(false);
 readonly me=signal<Me|null>(null);readonly suggestions=signal<Suggestions|null>(null);
 private token='';code='';
 private headers(){return {headers:new HttpHeaders({Authorization:`Bearer ${this.token}`})};}
 async verify(){this.busy.set(true);this.error.set('');this.message.set('');try{
  const session=await firstValueFrom(this.http.post<{access_token:string}>('/api/v1/candidate-portal/verify',{code:this.code}));
  this.code='';this.token=session.access_token;
  await this.loadMe();
 }catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async loadMe(){this.me.set(await firstValueFrom(this.http.get<Me>('/api/v1/candidate-portal/me',this.headers())));
  if(this.me()?.training_consent)await this.loadSuggestions();}
 async loadSuggestions(){if(!this.token)return;this.busy.set(true);try{
  this.suggestions.set(await firstValueFrom(this.http.get<Suggestions>('/api/v1/candidate-portal/training-suggestions',this.headers())));
 }catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async setConsent(consent:boolean){if(!this.token||!this.me())return;this.busy.set(true);this.error.set('');this.message.set('');try{
  await firstValueFrom(this.http.put('/api/v1/candidate-portal/consent',{consent,notice_version:this.me()!.notice_version},this.headers()));
  this.me.update(current=>current?{...current,training_consent:consent}:null);
  this.message.set(consent?'Accord enregistré. Vous pouvez le retirer à tout moment.':'Votre accord a été retiré.');
  this.suggestions.set(null);if(consent)await this.loadSuggestions();
 }catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async logout(){if(this.token){try{await firstValueFrom(this.http.post('/api/v1/candidate-portal/logout',{},this.headers()));}catch{ /* local session still cleared */ }}
  this.token='';this.me.set(null);this.suggestions.set(null);this.message.set('Session fermée.');}
}
