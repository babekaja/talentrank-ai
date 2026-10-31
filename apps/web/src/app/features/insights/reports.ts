import { VisualGuide } from '../../shared/ui/visual-guide';
import { NativeChart } from '../../shared/ui/native-chart';
import type { ChartDatum } from '../../shared/ui/native-chart';
import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { apiError, Campaign, Page } from '../../shared/recruitment';
import { EmptyState } from '../../shared/ui/empty-state';

interface History {id:string;campaign_id:string;run_id:string;format:string;row_count:number;sha256:string;created_at:string}
type Format = 'csv'|'xlsx'|'pdf';
@Component({selector:'tr-reports',standalone:true,imports:[VisualGuide, TrIcon,NativeChart,EmptyState],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="reports" [size]="15"/> Rapports et partage</p><h1>Télécharger un rapport de recrutement</h1><p>Choisissez un recrutement et téléchargez un document facile à partager avec votre équipe. Les avis humains et les éléments à vérifier restent clairement indiqués.</p></div><button class="btn-light" type="button" (click)="load()" [disabled]="loading() || busy()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Actualiser</button></header>
<tr-visual-guide title="Contenu des rapports" description="Le rapport reprend le même classement et les mêmes pourcentages pondérés que l’analyse des CV." />
@if(error()){<div class="alert-error mb-5" role="alert">{{error()}} <button class="underline font-semibold ml-2" type="button" (click)="load()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Réessayer</button></div>}
@if(info()){<div class="alert-ok mb-5" role="status">{{info()}}</div>}
<div class="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(290px,.8fr)]">
<section class="card p-6 sm:p-7"><div class="flex items-center gap-3 mb-6"><span class="step-number">1</span><div><h2 class="section-heading">Choisir votre rapport</h2><p class="section-caption mt-1">Choisissez la campagne et le format de consultation.</p></div></div>
<div class="space-y-5"><div><label class="field-label" for="report-campaign">Campagne concernée</label><select id="report-campaign" class="field" [disabled]="busy()" [value]="campaign()" (change)="campaign.set($any($event.target).value);runId.set('')"><option value="">Choisir une campagne</option>@for(x of campaigns();track x.id){<option [value]="x.id">{{x.name}}</option>}</select>@if(selectedCampaign();as c){<p class="mt-2 text-xs muted">Statut actuel : {{statusLabel(c.status)}}. Seules les analyses terminées peuvent être exportées.</p>}</div>
<fieldset [disabled]="busy()"><legend class="field-label">Format de sortie</legend><div class="grid grid-cols-3 gap-2">@for(item of formats;track item.value){<button type="button" class="option-tile" [class.option-tile-selected]="format()===item.value" [attr.aria-pressed]="format()===item.value" (click)="format.set(item.value)"><span class="block font-bold">{{item.title}}</span><span class="block text-xs mt-1 muted">{{item.hint}}</span></button>}</div></fieldset>
@if(runId()){<p class="text-sm muted">Classement de l’analyse {{runId().slice(0,8)}} sélectionnée depuis l’analyse des CV.</p>}
<div class="soft-panel p-4 text-sm"><strong class="block mb-1">Contenu de l'export</strong><p class="muted leading-relaxed">Classement des CV du pourcentage pondéré le plus élevé au plus faible, avec le rang et les critères restant à vérifier. Le pourcentage mesure la correspondance documentaire au poste.</p></div>
<button type="button" class="btn-primary w-full sm:w-auto" [disabled]="!campaign() || busy() || loading()" (click)="download()">{{busy()?'Préparation du fichier…':'Générer et télécharger le rapport'}}</button></div>
</section>
<aside class="card p-6 sm:p-7"><h2 class="section-heading">En un coup d'œil</h2><div class="mt-5 space-y-3"><div class="soft-panel px-4 py-4"><p class="meta-label">Campagnes accessibles</p><p class="text-3xl font-bold mt-2">{{campaigns().length}}</p></div><div class="soft-panel px-4 py-4"><p class="meta-label">Exports récents</p><p class="text-3xl font-bold mt-2">{{history().length}}</p></div></div><p class="mt-5 section-caption">Chaque export est journalisé. Vérifiez les destinataires avant de transmettre un document contenant des informations sur les candidats.</p>
@if(history().length){<div class="mt-5 border-t border-slate-200 pt-4 dark:border-slate-700"><h3 class="text-sm font-semibold">Rapports téléchargés par format</h3><tr-native-chart kind="donut" [height]="238" [data]="formatChart()" description="Répartition des formats parmi les derniers rapports chargés"/><p class="text-xs muted">Sur les {{history().length}} derniers exports affichés.</p></div>}</aside>
</div>
<section class="card mt-6 overflow-hidden"><div class="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6 border-b border-slate-100 dark:border-slate-700"><div><h2 class="section-heading">Historique des rapports</h2><p class="section-caption mt-1">Les derniers exports autorisés pour votre organisation.</p></div><label class="text-sm font-semibold">Afficher <select class="field mt-1 !w-auto" [value]="historyFormat()" (change)="historyFormat.set($any($event.target).value)"><option value="all">Tous les formats</option><option value="pdf">PDF</option><option value="xlsx">Excel</option><option value="csv">CSV</option></select></label></div>
@if(loading()){<div class="p-7" role="status" aria-live="polite">Chargement des campagnes et de l'historique…</div>}
@else if(!filteredHistory().length){<tr-empty-state title="Aucun export à afficher" description="Choisissez une campagne et générez un premier rapport, ou changez le filtre de format."/>}
@else{<div class="overflow-x-auto"><table class="w-full min-w-[660px]"><thead class="table-head"><tr><th class="px-5 py-4">Rapport</th><th>Date</th><th>Dossiers</th><th>Informations du rapport</th></tr></thead><tbody>@for(h of filteredHistory();track h.id){<tr><td class="table-td"><span class="soft-badge">{{h.format.toUpperCase()}}</span><p class="mt-2 text-xs muted">Campagne {{campaignName(h.campaign_id)}}</p></td><td class="table-td">{{dateLabel(h.created_at)}}</td><td class="table-td font-semibold">{{h.row_count}}</td><td class="table-td"><details class="text-xs muted"><summary class="cursor-pointer font-semibold">Voir les détails techniques</summary><p class="mt-2 font-mono break-all">Empreinte du fichier : {{h.sha256}}</p><p class="mt-1 font-mono">Référence d’analyse : {{h.run_id.slice(0,8)}}</p></details></td></tr>}</tbody></table></div>}
</section>`})
export class Reports implements OnInit {
 private readonly http=inject(HttpClient);
 private readonly route=inject(ActivatedRoute);readonly runId=signal('');
 readonly campaigns=signal<Campaign[]>([]);readonly history=signal<History[]>([]);
 readonly campaign=signal('');readonly format=signal<Format>('pdf');readonly historyFormat=signal('all');
 readonly loading=signal(true);readonly busy=signal(false);readonly error=signal('');readonly info=signal('');
 readonly formats: {value:Format;title:string;hint:string}[]=[{value:'pdf',title:'PDF',hint:'À présenter'},{value:'xlsx',title:'Excel',hint:'À analyser'},{value:'csv',title:'CSV',hint:'À traiter'}];
 readonly selectedCampaign=computed(()=>this.campaigns().find(c=>c.id===this.campaign())??null);
 readonly filteredHistory=computed(()=>this.history().filter(h=>this.historyFormat()==='all'||h.format===this.historyFormat()));
 readonly formatChart=computed<ChartDatum[]>(()=>{const rows=this.history();return ['pdf','xlsx','csv'].map(f=>({label:f.toUpperCase(),value:rows.filter(x=>x.format===f).length})).filter(x=>x.value>0);});
 ngOnInit(){this.campaign.set(this.route.snapshot.queryParamMap.get('campaign')??'');this.runId.set(this.route.snapshot.queryParamMap.get('run')??'');void this.load();}
 statusLabel(status:string){return ({active:'Ouverte',closed:'Clôturée',draft:'Brouillon'} as Record<string,string>)[status]??status;}
 campaignName(id:string){return this.campaigns().find(c=>c.id===id)?.name??`#${id.slice(0,8)}`;}
 dateLabel(value:string){const d=new Date(value);return Number.isNaN(d.getTime())?value:new Intl.DateTimeFormat('fr-FR',{dateStyle:'medium',timeStyle:'short'}).format(d);}
 async load(){this.loading.set(true);this.error.set('');try{const [c,h]=await Promise.all([
   firstValueFrom(this.http.get<Page<Campaign>>('/api/v1/campaigns',{params:{limit:100}})),
   firstValueFrom(this.http.get<{items:History[]}>('/api/v1/reports/history',{params:{limit:100}}))]);
   this.campaigns.set(c.items);this.history.set(h.items);
   if(this.campaign() && !c.items.some(x=>x.id===this.campaign()))this.campaign.set('');
  }catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 async download(){if(!this.campaign()||this.busy())return;const campaign=this.campaign();const format=this.format();this.busy.set(true);this.error.set('');this.info.set('');
  try{let params=new HttpParams().set('format',format);if(this.runId())params=params.set('run_id',this.runId());
   const blob=await firstValueFrom(this.http.get(`/api/v1/reports/campaigns/${encodeURIComponent(campaign)}`,{params,responseType:'blob'}));
   if(!blob.size)throw new Error('Le fichier est vide. Veuillez vérifier les résultats de cette campagne.');
   const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;
   link.download=`talentrank-${campaign.slice(0,8)}.${format}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   this.info.set('Le rapport a été préparé et son téléchargement a été demandé.');await this.load();
  }catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
