import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { NativeChart } from '../../shared/ui/native-chart';
import type { ChartDatum } from '../../shared/ui/native-chart';
import { TrIcon } from '../../shared/ui/tr-icon';
import { apiError } from '../../shared/recruitment';
interface Metrics {hit_1:number;recall_10:number;ndcg_10:number;mrr_10:number}
interface Lab {queries:number;dataset_sha256:string;model_type:string;overall:Record<string,Metrics>;by_language:Record<string,{queries:number;metrics:Record<string,Metrics>}>;limitations:string[];validation_status:string}
interface LanguageStatus {code:string;status:string}
interface FairResult {invariant:boolean;variant_count:number;observed_skill_mentions:number;limitations:string[];status:string}
@Component({selector:'tr-africa-prooflab',standalone:true,imports:[NativeChart,TrIcon,FormsModule],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="chart-no-axes-column" [size]="16"/> Laboratoire scientifique</p><h1>TalentRank ProofLab</h1><p>Comparer la recherche classique et les méthodes hybrides sur des passages annotés. Ici, aucune métrique n'est une promesse de performance sur de véritables CV.</p></div><button type="button" class="btn-light" (click)="load()" [disabled]="busy()">Recalculer les mesures</button></header>
@if(error()){<div role="alert" class="alert-error mb-5">{{error()}}</div>}
@if(busy()){<div class="card p-8" role="status">Calcul des mesures sur le corpus synthétique…</div>}
@if(data();as d){<div class="alert-error mb-5">Mesures expérimentales sur {{d.queries}} requêtes fictives seulement. Aucun modèle neuronal n'a été évalué par cet écran.</div>
<div class="grid gap-5 lg:grid-cols-2"><section class="card p-6"><h2 class="section-heading">Pertinence du premier résultat (Hit@1)</h2><p class="section-caption mt-2">Pourcentage de requêtes dont la première preuve retrouvée est annotée pertinente.</p><tr-native-chart kind="bars" [data]="hitChart()" [height]="270" description="Comparaison BM25, TF-IDF et fusion RRF sur exemples fictifs"/></section>
<section class="card p-6"><h2 class="section-heading">Comparaison selon la langue</h2><p class="section-caption mt-2">Français et anglais analysés séparément pour éviter qu'une moyenne cache leurs différences.</p><tr-native-chart kind="bars" [data]="languageChart()" [height]="270" description="Hit@1 de TF-IDF sur les exemples français et anglais"/></section></div>
<section class="card mt-5 p-6"><h2 class="section-heading">Résultats détaillés et reproductibles</h2><div class="overflow-x-auto mt-4"><table class="w-full min-w-[620px]"><thead class="table-head"><tr><th class="p-3">Méthode</th><th>Hit@1</th><th>Recall@10</th><th>nDCG@10</th><th>MRR@10</th></tr></thead><tbody>@for(m of methods;track m.key){<tr><td class="table-td font-semibold">{{m.label}}</td><td class="table-td">{{percent(d.overall[m.key].hit_1)}}</td><td class="table-td">{{percent(d.overall[m.key].recall_10)}}</td><td class="table-td">{{percent(d.overall[m.key].ndcg_10)}}</td><td class="table-td">{{percent(d.overall[m.key].mrr_10)}}</td></tr>}</tbody></table></div>
<details class="mt-5 text-sm"><summary class="font-semibold cursor-pointer">Méthode, limites et empreinte du jeu de test</summary><p class="mt-3 text-xs font-mono break-all">SHA-256 : {{d.dataset_sha256}}</p><ul class="list-disc pl-5 mt-2">@for(note of d.limitations;track note){<li>{{note}}</li>}</ul></details></section>}
<section class="card mt-6 p-6"><h2 class="section-heading">Langues et limites</h2><p class="section-caption mt-2">Disponibilité technique de la détection, pas validation scientifique sur des candidatures réelles.</p><div class="grid gap-3 sm:grid-cols-3 mt-4">@for(l of languages();track l.code){<div class="soft-panel p-4"><strong>{{languageName(l.code)}}</strong><p class="text-xs muted mt-2">{{languageStatus(l.status)}}</p></div>}</div></section>
<section class="card mt-6 p-6"><h2 class="section-heading">FairRank : contrôle expérimental d'invariance</h2><p class="section-caption mt-2">Ce contrôle vérifie que notre fonction de reconnaissance n'utilise pas le nom comme variable d'analyse. Cela ne démontre PAS l'absence de discrimination ou de biais indirects.</p>
@if(!isAdmin()){<p class="mt-4 section-caption">Ce test est réservé à l'administration.</p>}
@else{<label class="block mt-4"><span class="field-label">Texte professionnel fictif</span><textarea class="field" rows="3" maxlength="4000" [(ngModel)]="professionalText" placeholder="Ex. Développement d'une API REST avec FastAPI."></textarea></label>
<button type="button" class="btn-primary mt-3" (click)="runFairness()" [disabled]="fairBusy()||professionalText.trim().length<5">{{fairBusy()?'Contrôle…':'Exécuter le contrôle fictif'}}</button>
@if(fairResult();as f){<p class="mt-4 font-semibold">{{f.invariant?'Signal stable dans ce test contrôlé':'Variation détectée'}}</p><p class="section-caption mt-2">{{f.variant_count}} variantes d'identité fictives, {{f.observed_skill_mentions}} mention(s) reconnue(s).</p><ul class="list-disc pl-5 mt-3 text-sm">@for(l of f.limitations;track l){<li>{{l}}</li>}</ul>}
}</section>`})
export class ProofLab implements OnInit {
 private http=inject(HttpClient);private auth=inject(AuthService);
 readonly data=signal<Lab|null>(null);readonly error=signal('');readonly busy=signal(true);
 readonly languages=signal<LanguageStatus[]>([]);readonly fairBusy=signal(false);readonly fairResult=signal<FairResult|null>(null);
 readonly methods=[{key:'bm25',label:'BM25'},{key:'tfidf',label:'TF-IDF'},{key:'rrf',label:'Fusion RRF'}];
 professionalText='Développement et maintenance d’API REST avec FastAPI et MySQL.';
 readonly hitChart=computed<ChartDatum[]>(()=>this.methods.map(m=>({label:m.label,value:Math.round((this.data()?.overall[m.key]?.hit_1??0)*10000)/100})));
 readonly languageChart=computed<ChartDatum[]>(()=>Object.entries(this.data()?.by_language??{}).map(([k,v])=>({label:k==='fr'?'Français':'Anglais',value:Math.round((v.metrics['tfidf']?.hit_1??0)*10000)/100})));
 isAdmin(){return this.auth.user()?.role==='org_admin';}
 languageName(v:string){return ({fr:'Français',en:'Anglais',sw:'Swahili'} as Record<string,string>)[v]??v;}
 languageStatus(v:string){return v.startsWith('experimental')?'Expérimental : non activé pour le matching':'Détection lexicale disponible, fiabilité non validée';}
 percent(v:number){return `${(v*100).toFixed(1)} %`;}
 ngOnInit(){void this.load();}
 async load(){this.busy.set(true);this.error.set('');try{const [benchmark,lang]=await Promise.all([firstValueFrom(this.http.get<Lab>('/api/v1/africa/prooflab/benchmark')),firstValueFrom(this.http.get<{languages:LanguageStatus[]}>('/api/v1/africa/multilingual/status'))]);this.data.set(benchmark);this.languages.set(lang.languages);}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async runFairness(){if(!this.isAdmin())return;this.fairBusy.set(true);this.error.set('');this.fairResult.set(null);try{this.fairResult.set(await firstValueFrom(this.http.post<FairResult>('/api/v1/africa/fairrank/identity-check',{professional_text:this.professionalText,synthetic_identity_labels:['Profil fictif A','Profil fictif B']})));}catch(e){this.error.set(apiError(e));}finally{this.fairBusy.set(false);}}
}
