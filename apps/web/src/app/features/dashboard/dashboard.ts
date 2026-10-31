import { NativeChart, ChartDatum } from '../../shared/ui/native-chart';
import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { apiError } from '../../shared/recruitment';
import { EmptyState } from '../../shared/ui/empty-state';
import { LoadingState } from '../../shared/ui/loading-state';

interface Overview {
  cards: Record<string, number>;
  document_states: { status: string; count: number }[];
  campaigns: { id: string; name: string; applications: number }[];
  applications_daily: { day: string; count: number }[];
  skills_demanded: { label: string; count: number }[];
}

@Component({
  selector: 'tr-dashboard', standalone: true,
  imports: [TrIcon, NativeChart, RouterLink, EmptyState, LoadingState],
  template: `
<header class="page-intro dashboard-intro">
  <div class="dashboard-intro__content"><p class="eyebrow">Votre espace de recrutement</p><h1>Vue d’ensemble</h1><p>Retrouvez vos candidatures et les dossiers qui attendent votre équipe.</p></div>
  <div class="dashboard-intro__actions"><button type="button" class="icon-button dashboard-refresh" [disabled]="loading()" (click)="load()" aria-label="Actualiser le tableau de bord" title="Actualiser"><tr-icon name="refresh" [size]="18"/></button><a class="btn-primary" routerLink="/offres/nouvelle"><tr-icon name="plus" [size]="17"/> Créer une offre</a></div>
</header>
@if(error()){<div role="alert" class="alert-error mb-5 flex flex-wrap items-center justify-between gap-3"><span>{{error()}}</span><button class="btn-light" type="button" (click)="load()">Réessayer</button></div>}
@if(loading()){<tr-loading-state label="Chargement du tableau de bord"/>}
@else if(data(); as d){
  <section class="dashboard-metrics" aria-label="Chiffres clés de votre organisation">
    @for(card of cards.slice(0,4); track card.key){
      <a [routerLink]="card.path" class="dashboard-metric" [attr.aria-label]="card.label + ' : ' + formatNumber(d.cards[card.key]??0)">
        <div class="dashboard-metric__top"><span>{{card.label}}</span><tr-icon [name]="card.icon??'file'" [size]="18"/></div>
        <strong class="dashboard-metric__value">{{formatNumber(d.cards[card.key]??0)}}</strong>
        <div class="dashboard-metric__foot"><span>{{card.hint}}</span><tr-icon name="arrow-up-right" [size]="16"/></div>
      </a>
    }
  </section>
  @if(hasNextStep(d)){
    <section class="dashboard-attention" aria-label="Dossiers à traiter">
      <span class="dashboard-attention__icon"><tr-icon [name]="(d.cards['documents_failed']??0)>0?'alert':'clipboard'" [size]="21"/></span>
      <div class="dashboard-attention__text"><h2>{{nextStepTitle(d)}}</h2><p>{{nextStepDescription(d)}}</p></div>
      <a [routerLink]="nextStepRoute(d)" class="dashboard-attention__action">{{nextStepAction(d)}} <tr-icon name="arrow-right" [size]="17"/></a>
    </section>
  }
  @if((d.cards['jobs']??0)===0 && (d.cards['applications']??0)===0){<div class="dashboard-guide mb-6 flex flex-wrap items-center justify-between gap-3 px-4 py-3"><p class="text-sm">Vous débutez ? Le guide explique comment préparer votre première campagne.</p><a class="inline-link text-sm" routerLink="/demarrer">Voir le guide</a></div>}
  <div class="dashboard-panels">
    <section class="card dashboard-chart dashboard-activity" aria-labelledby="applications-chart">
      <div class="dashboard-panel-heading"><div><h2 id="applications-chart">Candidatures reçues</h2><p>Évolution des réceptions par jour</p></div><span class="dashboard-panel-label">Activité</span></div>
      @if(!d.applications_daily.length){<tr-empty-state title="Pas encore de candidatures" description="Les réceptions apparaîtront ici dès qu'une campagne recevra des dossiers." actionLabel="Voir les campagnes" actionRoute="/campagnes"/>}
      @else{<tr-native-chart kind="trend" [data]="trendChart()" [height]="260" [description]="chartSummary(d)"/>}
    </section>
    <section class="card dashboard-chart dashboard-documents" aria-labelledby="documents-chart">
      <div class="dashboard-panel-heading"><div><h2 id="documents-chart">Traitement des CV</h2><p>État des documents importés</p></div><a routerLink="/importations" class="icon-button" aria-label="Ouvrir les importations"><tr-icon name="arrow-up-right" [size]="17"/></a></div>
      @if(!d.document_states.length){<tr-empty-state title="Aucun document importé" description="Déposez vos premiers CV pour en extraire le texte." actionLabel="Importer des CV" actionRoute="/importations"/>}
      @else{<tr-native-chart kind="donut" totalLabel="CV importés" [data]="documentChart()" [height]="260" description="Répartition des statuts des documents"/>}
    </section>
    <section class="card dashboard-chart dashboard-campaigns" aria-labelledby="campaigns-card">
      <div class="dashboard-panel-heading"><div><h2 id="campaigns-card">Campagnes en activité</h2><p>Répartition des candidatures</p></div><a routerLink="/campagnes" class="inline-link text-sm">Tout voir <tr-icon name="arrow-right" [size]="15"/></a></div>
      @if(!d.campaigns.length){<tr-empty-state title="Aucune campagne pour le moment" description="Créez une offre et confirmez ses critères pour ouvrir une campagne." actionLabel="Créer une offre" actionRoute="/offres/nouvelle"/>}
      @else{<div class="campaign-overview">@for(x of d.campaigns.slice(0,5); track x.id){<div class="campaign-overview__row"><div class="campaign-overview__heading"><span [title]="x.name">{{x.name}}</span><strong>{{formatNumber(x.applications)}} <small>{{x.applications===1?'dossier':'dossiers'}}</small></strong></div><div class="campaign-overview__track" aria-hidden="true"><span [style.width.%]="campaignShare(x.applications,d)"></span></div></div>}</div>}
    </section>
    <section class="card dashboard-chart dashboard-skills" aria-labelledby="skills-card">
      <div class="dashboard-panel-heading"><div><h2 id="skills-card">Compétences recherchées</h2><p>Occurrences dans les critères des offres</p></div><a routerLink="/competences" class="icon-button" aria-label="Ouvrir le référentiel des compétences"><tr-icon name="arrow-up-right" [size]="17"/></a></div>
      @if(!d.skills_demanded.length){<tr-empty-state title="Aucun critère confirmé" description="Les compétences apparaîtront lorsque vous confirmerez les critères d'une offre." actionLabel="Voir les offres" actionRoute="/offres"/>}
      @else{<tr-native-chart kind="bars" [data]="skillChart()" [height]="300" description="Compétences les plus demandées"/>}
    </section>
  </div>
  <details class="dashboard-extra">
    <summary>Autres indicateurs <span>Offres, documents et examens terminés</span></summary>
    <div class="dashboard-extra__grid">@for(card of cards.slice(4); track card.key){<a [routerLink]="card.path"><span>{{card.label}}</span><strong>{{formatNumber(d.cards[card.key]??0)}}</strong><small>{{card.hint}}</small></a>}</div>
  </details>
}
`})
export class Dashboard implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly numberFormat = new Intl.NumberFormat('fr-FR');
  readonly data = signal<Overview | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly trendChart = computed<ChartDatum[]>(() => this.data()?.applications_daily.map(x => ({label:x.day,value:x.count})) ?? []);
  readonly documentChart = computed<ChartDatum[]>(() => this.data()?.document_states.map(x => ({label:this.stateLabel(x.status),value:x.count})) ?? []);
  readonly skillChart = computed<ChartDatum[]>(() => this.data()?.skills_demanded.slice(0,6).map(x => ({label:x.label,value:x.count})) ?? []);
  readonly cards = [
    {key:'campaigns_active',label:'Campagnes ouvertes',hint:'Recrutements en cours',path:'/campagnes',icon:'briefcase'},
    {key:'applications',label:'Candidatures reçues',hint:'Tous les dossiers enregistrés',path:'/candidatures',icon:'people'},
    {key:'applications_to_review',label:'À examiner',hint:'En attente d’un avis',path:'/affectations',icon:'clipboard'},
    {key:'documents_failed',label:'CV à reprendre',hint:'Erreurs de traitement',path:'/importations',icon:'file'},
    {key:'jobs',label:'Offres créées',hint:'Besoins définis',path:'/offres'},
    {key:'documents',label:'CV importés',hint:'Documents déposés',path:'/importations'},
    {key:'applications_human_reviewed',label:'Avis humains',hint:'Dossiers examinés',path:'/affectations'},
    {key:'analyses_completed',label:'Comparaisons terminées',hint:'Correspondances calculées',path:'/matching'}
  ];
  ngOnInit(){void this.load();}
  async load(){this.loading.set(true);this.error.set('');try{this.data.set(await firstValueFrom(this.http.get<Overview>('/api/v1/dashboard/overview')));}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
  formatNumber(value:number){return this.numberFormat.format(value);}
  campaignShare(value:number,d:Overview){const max=Math.max(1,...d.campaigns.map(x=>x.applications));return value/max*100;}
  stateLabel(v:string){return ({pending:'En attente',processing:'En cours',completed:'Extraits',needs_review:'À vérifier',failed:'Erreurs'} as Record<string,string>)[v]??v.replaceAll('_',' ');}
  chartSummary(d:Overview){return 'Candidatures journalières : '+d.applications_daily.map(x=>`${x.day} ${x.count}`).join(', ');}
  hasNextStep(d:Overview){return (d.cards['documents_failed']??0)>0 || (d.cards['applications_to_review']??0)>0 || (d.cards['campaigns_active']??0)===0;}
  nextStepTitle(d:Overview){const failed=d.cards['documents_failed']??0;if(failed>0)return `${this.formatNumber(failed)} CV à reprendre`;const pending=d.cards['applications_to_review']??0;if(pending>0)return `${this.formatNumber(pending)} ${pending===1?'candidature attend':'candidatures attendent'} un avis`;return 'Ouvrez une campagne de recrutement';}
  nextStepDescription(d:Overview){if((d.cards['documents_failed']??0)>0)return 'Consultez les erreurs pour relancer le traitement des documents.';if((d.cards['applications_to_review']??0)>0)return 'Répartissez les dossiers entre les membres de votre équipe.';return 'Définissez les critères du poste avant de recevoir des candidatures.';}
  nextStepRoute(d:Overview){if((d.cards['documents_failed']??0)>0)return '/importations';if((d.cards['applications_to_review']??0)>0)return '/affectations';return '/offres/nouvelle';}
  nextStepAction(d:Overview){if((d.cards['documents_failed']??0)>0)return 'Voir les documents';if((d.cards['applications_to_review']??0)>0)return 'Examiner les dossiers';return 'Créer une offre';}
}
