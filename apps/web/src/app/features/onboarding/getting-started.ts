import { Component, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { apiError } from '../../shared/recruitment';
import { TrIcon } from '../../shared/ui/tr-icon';
import { LoadingState } from '../../shared/ui/loading-state';

/** A guide derived from live organisation data. It never creates fake progress. */
interface Overview { cards: Record<string,number>; note?:string }
interface GuideStep { number:number; icon:string; title:string; explanation:string; action:string; url:string; countKey:string; countLabel:string }
@Component({
 selector:'tr-getting-started',standalone:true,imports:[TrIcon,RouterLink,LoadingState],
 template:`
 <header class="page-intro">
  <div><p class="eyebrow"><tr-icon name="help" [size]="16"/> Un guide à votre rythme</p>
   <h1>Comment recruter avec TalentRank ?</h1>
   <p>Pas besoin de connaître l'informatique. Suivez ces étapes pour préparer un recrutement, recevoir les CV et examiner les candidatures.</p>
  </div>
  <a routerLink="/tableau-de-bord" class="btn-light"><tr-icon name="arrow-left" [size]="17"/> Retour à l'accueil</a>
 </header>
 <section class="human-callout mb-7 p-5 sm:p-6" aria-label="Principe important">
  <div class="flex items-start gap-4">
   <span class="flex-none flex items-center justify-center w-11 h-11 rounded-[14px] bg-[#d3ece5] text-[#166552] dark:bg-[#1f4a3e] dark:text-[#8de1c3]"><tr-icon name="shield" [size]="22"/></span>
   <div>
    <h2 class="font-bold text-base">Vous prenez toujours les décisions.</h2>
    <p class="mt-1 text-sm leading-relaxed">TalentRank aide à repérer des informations présentes dans les CV. Il peut se tromper ou manquer des éléments. Aucun candidat n'est embauché ou écarté automatiquement.</p>
   </div>
  </div>
 </section>
 @if(error()){<div role="alert" class="alert-error mb-5">{{error()}} <button type="button" class="underline" (click)="load()">Réessayer</button></div>}
 @if(loading()){<tr-loading-state label="Vérification de votre activité…"/>}
 @else {
  <section class="mb-7">
   <div class="flex flex-wrap items-end justify-between gap-3 mb-5">
    <div>
     <p class="meta-label">Progression</p>
     <h2 class="section-heading mt-1">Votre parcours en 5 étapes</h2>
     <p class="section-caption mt-1">Les repères ci-dessous sont calculés avec les informations de votre entreprise, et non avec des données de démonstration.</p>
    </div>
    <button type="button" class="btn-light" (click)="load()"><tr-icon name="refresh" [size]="17"/> Actualiser</button>
   </div>
   <div class="grid gap-4 lg:grid-cols-2">
   @for(step of steps;track step.number){
    <article class="card guide-step-card flex flex-col p-5 sm:p-6 card-hover">
     <div class="flex items-start gap-4">
      <span class="step-number shrink-0 text-lg">{{step.number}}</span>
      <div class="min-w-0 flex-1">
       <h3 class="text-[17px] font-bold tracking-tight leading-snug">{{step.title}}</h3>
       <p class="section-caption mt-2 leading-relaxed">{{step.explanation}}</p>
      </div>
      <span class="flex-none flex items-center justify-center w-9 h-9 rounded-[11px] bg-[#eaf2f5] text-[#245b93] dark:bg-[#1d3d52] dark:text-[#a8d4ef]"><tr-icon [name]="step.icon" [size]="19"/></span>
     </div>
     <div class="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 dark:border-slate-700">
      @if(data();as overview){
       <span class="tag">{{step.countLabel}} : <strong class="text-[var(--tr-ink)]">{{overview.cards[step.countKey]??0}}</strong></span>
      }@else{
       <span class="text-xs muted">Consultez cet espace pour suivre votre activité.</span>
      }
      <a class="btn-light text-sm" [routerLink]="step.url">{{step.action}} <tr-icon name="arrow-right" [size]="15"/></a>
     </div>
    </article>
   }
   </div>
  </section>
 }
 <section class="card p-5 sm:p-6" aria-labelledby="words-title">
  <div class="mb-4 flex items-center gap-3">
   <span class="flex items-center justify-center w-9 h-9 rounded-[11px] bg-[#eaf2f5] text-[#245b93] dark:bg-[#1d3d52] dark:text-[#a8d4ef]"><tr-icon name="book" [size]="18"/></span>
   <h2 id="words-title" class="section-heading">Les mots utiles, expliqués simplement</h2>
  </div>
  <div class="divide-y divide-slate-100 dark:divide-slate-700">
   @for(term of vocabulary;track term.word){
    <details class="py-3.5 group">
     <summary class="cursor-pointer select-none font-semibold text-sm flex items-center justify-between gap-3">
      <span>{{term.word}}</span>
      <span class="text-slate-400 group-open:rotate-45 transition-transform duration-150 font-normal text-base" aria-hidden="true">+</span>
     </summary>
     <p class="section-caption mt-2.5 pl-1">{{term.explanation}}</p>
    </details>
   }
  </div>
 </section>
 `
})
export class GettingStarted implements OnInit {
 private readonly http=inject(HttpClient);
 readonly loading=signal(true);readonly error=signal('');readonly data=signal<Overview|null>(null);
 readonly steps:GuideStep[]=[
  {number:1,icon:'briefcase',title:'Définir le poste',explanation:'Écrivez ce que la personne fera et les compétences nécessaires. Vous validerez vous-même ces critères.',action:'Voir mes offres',url:'/offres',countKey:'jobs',countLabel:'Offres créées'},
  {number:2,icon:'clipboard',title:'Ouvrir le recrutement',explanation:'Associez votre offre à une campagne pour recevoir et organiser les candidatures.',action:'Voir mes recrutements',url:'/campagnes',countKey:'campaigns_active',countLabel:'Campagnes ouvertes'},
  {number:3,icon:'file',title:'Ajouter les CV',explanation:'Déposez les PDF ou documents Word. TalentRank conserve les fichiers de manière privée et essaie d’en lire le texte.',action:'Déposer des CV',url:'/importations',countKey:'documents',countLabel:'CV reçus'},
  {number:4,icon:'compare',title:'Consulter les résultats',explanation:'Examinez les compétences mentionnées dans les CV et ouvrez les passages qui ont servi au calcul. Les informations incertaines sont signalées.',action:'Voir les résultats',url:'/matching',countKey:'analyses_completed',countLabel:'Analyses terminées'},
  {number:5,icon:'people',title:'Examiner avec votre équipe',explanation:'Répartissez les dossiers, prenez connaissance des preuves, puis enregistrez les avis humains.',action:'Répartir les dossiers',url:'/affectations',countKey:'applications_human_reviewed',countLabel:'Dossiers examinés'}
 ];
 readonly vocabulary=[
  {word:'Campagne',explanation:'Un recrutement ouvert pour un poste donné. Elle regroupe les candidatures et leur suivi.'},
  {word:'Compétence documentée',explanation:'Une compétence mentionnée dans un passage du CV. Cela ne prouve pas automatiquement le niveau de maîtrise.'},
  {word:'Correspondance',explanation:'Une comparaison entre les critères du poste et ce que contient le CV. Ce n’est pas une probabilité d’embauche.'},
  {word:'À vérifier',explanation:'Le système n’a pas assez d’informations pour conclure. Une personne doit examiner le document ou poser une question.'},
  {word:'Analyse automatique',explanation:'La lecture et la comparaison assistées par ordinateur, avec des erreurs possibles. La décision finale reste humaine.'}
 ];
 ngOnInit(){void this.load();}
 async load(){this.loading.set(true);this.error.set('');try{this.data.set(await firstValueFrom(this.http.get<Overview>('/api/v1/dashboard/overview')));}catch(e){this.data.set(null);this.error.set('Impossible de consulter les chiffres pour le moment. Vous pouvez quand même suivre les étapes ci-dessous.');}finally{this.loading.set(false);}}
}
