import { Component, DestroyRef, HostListener, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs';
import { LucideLayoutDashboard, LucideLayers3, LucideBriefcaseBusiness, LucideUsers, LucideContact, LucideClipboardList, LucideUserCog, LucideScrollText, LucideLogOut, LucideMoon, LucideSun, LucideMenu, LucideX, LucideLock, LucideUpload, LucideBrain, LucideSearch, LucideShieldCheck } from '@lucide/angular';
import { AuthService } from '../../core/auth/auth.service';
import { PreferencesService } from '../../core/ui/preferences.service';

@Component({selector:'tr-shell',standalone:true,
 imports:[RouterOutlet,RouterLink,RouterLinkActive,LucideLayoutDashboard,LucideLayers3,LucideBriefcaseBusiness,LucideUsers,LucideContact,LucideClipboardList,LucideUserCog,LucideScrollText,LucideLogOut,LucideMoon,LucideSun,LucideMenu,LucideX,LucideLock,LucideUpload,LucideBrain,LucideSearch,LucideShieldCheck],
 template:`
 <a href="#main-content" class="skip-link">Aller directement au contenu</a>
 <div class="app-frame min-h-screen text-slate-800 dark:text-slate-100 lg:flex">
  @if(menu()){<button type="button" class="fixed inset-0 z-30 bg-[#12283d]/70 lg:hidden" aria-label="Fermer la navigation" (click)="closeMenu()"></button>}
  <aside id="main-menu" [class.-translate-x-full]="!menu()" class="app-sidebar fixed inset-y-0 left-0 z-40 flex w-[260px] flex-col border-r border-[#e4e9ea] shadow-xl transition-transform duration-200 dark:border-slate-700 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 lg:shadow-none" aria-label="Navigation principale">
   <div class="flex min-h-[88px] items-center justify-between gap-2 px-5">
    <a routerLink="/" class="workspace-brand flex items-center gap-3" aria-label="TalentRank AI, accueil" (click)="closeMenu()"><span class="workspace-brand__mark inline-flex h-11 w-11 items-center justify-center rounded-[15px] text-white"><svg lucideLayers3 [size]="23" /></span><span><strong class="block text-lg tracking-[-.03em]">TalentRank <span class="workspace-brand__accent">AI</span></strong><span class="workspace-brand__tagline block text-[11px]">Suivi des candidatures</span></span></a>
    <button type="button" class="icon-button lg:hidden" aria-label="Fermer" (click)="closeMenu()"><svg lucideX [size]="21"/></button>
   </div>
   <div class="workspace-organization mx-4 mt-2 rounded-2xl border border-[#e2e8e9] bg-[#f6f8f7] px-4 py-3.5 dark:border-slate-700 dark:bg-[#1b3040]"><p class="meta-label text-[10px]">Votre organisation</p><div class="mt-2 flex items-center gap-2.5"><div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px] bg-[#1d4e66] text-white text-[11px] font-bold leading-none">{{(auth.user()?.organization_name || 'E')[0].toUpperCase()}}</div><div class="min-w-0"><p class="truncate text-sm font-bold leading-snug">{{auth.user()?.organization_name || 'Espace entreprise'}}</p><p class="text-[11px] text-slate-500 dark:text-slate-300 leading-tight mt-0.5">{{roleLabel(auth.user()?.role)}}</p></div></div></div>
   <nav class="workspace-sidebar-nav mt-2 min-h-0 flex-1 overflow-y-auto px-3 pb-5" aria-label="Rubriques">
    @if(canRecruit()) {
     <p class="nav-group">Recrutement</p>
     <a routerLink="/tableau-de-bord" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideLayoutDashboard [size]="18"/> Vue d’ensemble</a>
     <a routerLink="/offres" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideBriefcaseBusiness [size]="18"/> Offres d’emploi</a>
     <a routerLink="/campagnes" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideClipboardList [size]="18"/> Campagnes</a>
     <a routerLink="/importations" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideUpload [size]="18"/> Importer des CV</a>
     <a routerLink="/candidatures" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideUsers [size]="18"/> Candidatures</a>
     <a routerLink="/matching" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideSearch [size]="18"/> Analyse des CV</a>
     <a routerLink="/rapports" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideScrollText [size]="18"/> Rapports</a>
     <button type="button" class="nav nav-expander mt-4 w-full" (click)="managementTools.update(v=>!v)" [attr.aria-expanded]="managementTools()" aria-controls="management-links"><svg lucideUserCog [size]="18"/> Organisation <span class="ml-auto text-xs" aria-hidden="true">{{managementTools()?'−':'+'}}</span></button>
     @if(managementTools()) {
      <div id="management-links" class="ml-2 border-l border-slate-200 pl-2 dark:border-slate-700">
       <a routerLink="/candidats" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideContact [size]="17"/> Répertoire des candidats</a>
       <a routerLink="/affectations" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideClipboardList [size]="17"/> Répartir les dossiers</a>
       <a routerLink="/formations" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideBriefcaseBusiness [size]="17"/> Formations disponibles</a>
       <a routerLink="/competences" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideBrain [size]="17"/> Compétences reconnues</a>
       @if(isAdmin()) {
        <a routerLink="/equipe" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideUserCog [size]="17"/> Membres de l'équipe</a>
        <a routerLink="/confidentialite" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideLock [size]="17"/> Vie privée des candidats</a>
        <a routerLink="/audit" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideScrollText [size]="17"/> Historique des actions</a>
       }
      </div>
     }
     <button type="button" class="nav nav-expander mt-2 w-full" (click)="advancedTools.update(v=>!v)" [attr.aria-expanded]="advancedTools()" aria-controls="expert-links"><svg lucideBrain [size]="18"/> Outils de recherche <span class="ml-auto text-xs" aria-hidden="true">{{advancedTools()?'−':'+'}}</span></button>
     @if(advancedTools()) {
      <div id="expert-links" class="ml-2 border-l border-slate-200 pl-2 dark:border-slate-700">
       <p class="px-3 pt-2 text-xs leading-relaxed text-slate-500">Pour les responsables techniques. Ces outils ne sont pas nécessaires pour examiner les CV.</p>
       <a routerLink="/talentgraph-africa" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideBrain [size]="17"/> Liens entre compétences</a>
       <a routerLink="/prooflab-africa" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideScrollText [size]="17"/> Tests de qualité de l'IA</a>
       <a routerLink="/laboratoire-ml" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideBrain [size]="17"/> Modèles expérimentaux</a>
       <a routerLink="/recherche-semantique" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideSearch [size]="17"/> Recherche avancée</a>
      </div>
     }
    }
    @if(isEvaluator()) {
     <p class="nav-group">Vos dossiers</p>
     <a routerLink="/mes-examens" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideClipboardList [size]="18"/> Dossiers à examiner</a>
    }
    <p class="nav-group">Ressources</p>
    <a routerLink="/demarrer" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideShieldCheck [size]="18"/> Guide de démarrage</a>
    <a routerLink="/parametres" routerLinkActive="nav-active" ariaCurrentWhenActive="page" (click)="closeMenu()" class="nav"><svg lucideUserCog [size]="18"/> Préférences</a>
   </nav>
   <div class="workspace-sidebar-foot border-t px-3 py-4"><button type="button" (click)="logout()" class="nav workspace-logout w-full"><svg lucideLogOut [size]="18"/> Se déconnecter</button></div>
  </aside>
  <div class="min-w-0 flex-1">
   <header class="workspace-header sticky top-0 z-20 flex min-h-[72px] items-center justify-between gap-3 border-b border-[#e4e9ea] bg-white/95 px-4 backdrop-blur dark:border-slate-700 dark:bg-[#142331]/95 sm:px-8">
    <div class="flex min-w-0 items-center gap-3"><button type="button" class="icon-button lg:hidden" (click)="openMenu()" aria-label="Ouvrir la navigation" [attr.aria-expanded]="menu()" aria-controls="main-menu"><svg lucideMenu [size]="21"/></button><div class="min-w-0"><p class="workspace-header__eyebrow text-[10px] font-semibold tracking-widest uppercase">{{auth.user()?.organization_name || 'Votre entreprise'}}</p><strong class="block truncate text-base font-bold tracking-tight sm:text-lg text-slate-900 dark:text-white">{{currentPage()}}</strong></div></div>
    <div class="flex shrink-0 items-center gap-2 sm:gap-3">
     <button type="button" class="icon-button" [attr.aria-label]="themeLabel()" [title]="themeLabel()" (click)="toggleTheme()">@if(prefs.isDark()){<svg lucideSun [size]="19"/>}@else{<svg lucideMoon [size]="19"/>}</button>
     <a routerLink="/parametres" class="workspace-profile" aria-label="Ouvrir mes préférences"><span class="workspace-profile__text"><strong>{{auth.user()?.full_name}}</strong><small>{{roleLabel(auth.user()?.role)}}</small></span><span class="workspace-avatar">{{initials()}}</span></a>
    </div>
   </header>
   @if(auth.user()?.demo_mode){<aside class="soft-panel mx-4 mt-5 flex flex-wrap items-center justify-between gap-3 p-4 sm:mx-8" aria-label="Session de démonstration"><div><p class="text-sm font-semibold">Mode démo · {{auth.user()?.organization_name}}</p><p class="mt-1 text-sm muted">{{auth.user()?.demo_read_only?'Consultation, comparaison et exports disponibles. Les données sont protégées contre les modifications.':'Cet espace de démonstration est partagé. Utilisez uniquement des données fictives.'}}</p></div><button type="button" class="btn-light shrink-0" (click)="logout()">Quitter la démo</button></aside>}
   @if(!online()){<div role="status" class="border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">Connexion interrompue. Vos données restent affichées, mais les actions nécessitant Internet sont indisponibles.</div>}
   <main id="main-content" tabindex="-1" class="workspace-main mx-auto w-full max-w-[1440px] px-4 py-8 pb-28 sm:px-8 sm:pb-8 lg:py-10"><router-outlet/></main>
   <footer class="workspace-footer mx-auto max-w-[1440px] px-4 pb-24 text-xs leading-relaxed text-slate-500 dark:text-slate-300 sm:px-8 sm:pb-9">TalentRank AI · Les résultats expliquent ce qui est documenté, ils ne remplacent pas le jugement humain.</footer>
   @if(canRecruit()){<nav class="workspace-mobile-nav sm:hidden" aria-label="Accès rapides"><a routerLink="/tableau-de-bord" routerLinkActive="is-active" ariaCurrentWhenActive="page"><svg lucideLayoutDashboard [size]="20"/> Accueil</a><a routerLink="/candidatures" routerLinkActive="is-active" ariaCurrentWhenActive="page"><svg lucideUsers [size]="20"/> Candidatures</a><a routerLink="/importations" routerLinkActive="is-active" ariaCurrentWhenActive="page"><svg lucideUpload [size]="20"/> Importer</a></nav>}
  </div>
 </div>`})
export class Shell {
 readonly auth=inject(AuthService); readonly prefs=inject(PreferencesService);
 private router=inject(Router); readonly menu=signal(false);
 readonly currentPage=signal('Tableau de bord'); readonly advancedTools=signal(false); readonly managementTools=signal(false);
 readonly online=signal(typeof navigator==='undefined'?true:navigator.onLine);
 private readonly names:Record<string,string>={offres:'Offres d’emploi',campagnes:'Campagnes',candidats:'Candidats',candidatures:'Candidatures',affectations:'Affectations',formations:'Formations','mes-examens':'Dossiers à examiner','tableau-de-bord':'Vue d’ensemble',importations:'Déposer des CV',competences:'Compétences',matching:'Résultats des CV',rapports:'Rapports','laboratoire-ml':'Laboratoire ML','recherche-semantique':'Recherche sémantique','talentgraph-africa':'Graphe de compétences','prooflab-africa':'Évaluation des méthodes',equipe:'Équipe',audit:'Historique des actions',confidentialite:'Confidentialité',parametres:'Mes préférences',demarrer:'Bien démarrer'};
 constructor(){this.router.events.pipe(filter(e=>e instanceof NavigationEnd),takeUntilDestroyed(inject(DestroyRef))).subscribe(()=>{this.updateTitle();this.closeMenu();});this.updateTitle();}
 private updateTitle(){
  const key=this.router.url.split('?')[0].split('/').filter(Boolean)[0];
  this.currentPage.set(this.names[key]??'Mon accueil');
  // Keep the active sub-navigation discoverable on direct links or refresh.
  if(['candidats','affectations','formations','competences','equipe','confidentialite','audit'].includes(key))this.managementTools.set(true);
  if(['talentgraph-africa','prooflab-africa','laboratoire-ml','recherche-semantique'].includes(key))this.advancedTools.set(true);
 }
 isEvaluator(){return this.auth.user()?.role==='evaluator';}
 isAdmin(){return this.auth.user()?.role==='org_admin';}
 canRecruit(){return this.isAdmin()||this.auth.user()?.role==='recruiter';}
 roleLabel(role:string|undefined){return ({org_admin:'Administrateur',recruiter:'Recruteur',evaluator:'Évaluateur'} as Record<string,string>)[role??'']??'Membre';}
 initials(){const name=this.auth.user()?.full_name??'';return name.split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0].toUpperCase()).join('')||'TR';}
 openMenu(){this.menu.set(true);}
 closeMenu(){this.menu.set(false);}
 @HostListener('window:online') onOnline(){this.online.set(true);}
 @HostListener('window:offline') onOffline(){this.online.set(false);}
 @HostListener('document:keydown.escape') onEscape(){this.closeMenu();}
 themeLabel(){return this.prefs.isDark()?'Passer au thème clair':'Passer au thème sombre';}
 toggleTheme(){this.prefs.setTheme(this.prefs.isDark()?'light':'dark');}
 async logout(){try{await this.auth.logout();}finally{void this.router.navigateByUrl('/connexion');}}
}
