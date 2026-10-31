import { HumanStatus } from '../../shared/ui/human-status';
import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { Page, apiError } from '../../shared/recruitment';
interface Evaluator {id:string;label:string;user_id:string}
interface Assignable {application_id:string;candidate_reference:string;campaign_name:string}
interface Assignment {id:string;application_id:string;evaluator_member_id:string;candidate_reference:string;campaign_name:string;status:string;created_at:string}
@Component({selector:'tr-assignments',standalone:true,imports:[HumanStatus,TrIcon,FormsModule],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="clipboard" [size]="15"/> Travail en équipe</p><h1 class="mt-2">Répartir les dossiers</h1><p>Confiez chaque candidature à un évaluateur identifié. Chacun verra uniquement les dossiers qui lui sont affectés et ses observations seront conservées.</p></div></header>
@if(error()){<p class="alert-error mb-4" role="alert">{{error()}}</p>}@if(success()){<p class="alert-ok mb-4" role="status">{{success()}}</p>}
<form class="card p-6 mb-6" (ngSubmit)="assign()"><h2 class="section-heading mb-1">Choisir un dossier et un évaluateur</h2><p class="section-caption mb-5">Les personnes sélectionnées pourront consulter les preuves documentaires nécessaires à leur examen.</p>
<div class="grid gap-4 lg:grid-cols-[1fr_1fr_auto]">
<div><label class="field-label" for="application">Candidature</label><select class="field" name="application" id="application" [(ngModel)]="applicationId" required><option value="">Sélectionner une candidature</option>@for(a of candidates();track a.application_id){<option [value]="a.application_id">{{a.candidate_reference}} · {{a.campaign_name}}</option>}</select><p class="text-xs text-slate-500 mt-2">{{availableTotal()}} candidature(s) · page {{availableOffset()/25+1}}</p><div class="flex gap-2 mt-2"><button class="btn-light" type="button" (click)="changeAvailable(-1)" [disabled]="availableOffset()===0">Précédent</button><button class="btn-light" type="button" (click)="changeAvailable(1)" [disabled]="availableOffset()+25>=availableTotal()"><tr-icon name="arrow-right" [size]="16" class="inline-flex align-middle mr-1"/>Suivant</button></div></div>
<label><span class="field-label">Évaluateur actif</span><select class="field" name="evaluator" [(ngModel)]="evaluatorId" required><option value="">Sélectionner un membre</option>@for(m of members();track m.id){<option [value]="m.id">{{m.label}}</option>}</select></label>
<button class="btn-primary self-start lg:mt-6" type="submit" [disabled]="busy() || !applicationId || !evaluatorId">Confier ce dossier</button></div>
@if(!members().length){<p class="text-sm mt-4 text-amber-700">Aucun évaluateur actif. Un administrateur doit attribuer ce rôle depuis l'espace Équipe.</p>}
</form>
<section class="card overflow-hidden"><div class="flex items-center justify-between gap-3 p-5 border-b border-slate-100 dark:border-slate-800"><h2 class="font-bold">Historique des affectations ({{total()}})</h2><button class="btn-light" [disabled]="loading()" (click)="load()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Actualiser</button></div>
@if(loading()){<p class="p-5" role="status">Chargement…</p>}@else if(!assignments().length){<div class="p-7 text-center"><h3 class="font-semibold">Aucun dossier réparti</h3><p class="section-caption mt-2">Choisissez une candidature et un membre de l’équipe pour commencer.</p></div>}@else{<div class="overflow-x-auto"><table class="w-full min-w-[640px] text-left text-sm"><thead class="table-head"><tr><th class="p-4">Référence</th><th>Campagne</th><th>Évaluateur</th><th>État</th><th>Action</th></tr></thead><tbody>@for(a of assignments();track a.id){<tr class="border-t border-slate-100 dark:border-slate-800"><td class="p-4 font-semibold">{{a.candidate_reference}}</td><td>{{a.campaign_name}}</td><td>{{memberName(a.evaluator_member_id)}}</td><td>{{a.status | humanStatus:'assignment'}}</td><td>@if(a.status!=='revoked'){<button class="text-rose-700 underline" [disabled]="busy()" (click)="revoke(a)">Révoquer</button>}</td></tr>}</tbody></table></div>}
<div class="flex justify-between items-center p-4"><span class="text-xs text-slate-500">{{total()}} affectation(s)</span><div class="flex gap-2"><button class="btn-light" [disabled]="offset()===0" (click)="changePage(-1)">Précédent</button><button class="btn-light" [disabled]="offset()+25>=total()" (click)="changePage(1)"><tr-icon name="arrow-right" [size]="16" class="inline-flex align-middle mr-1"/>Suivant</button></div></div>
</section>
`})
export class AssignmentsPage implements OnInit {
 private http=inject(HttpClient);readonly members=signal<Evaluator[]>([]);readonly candidates=signal<Assignable[]>([]);readonly assignments=signal<Assignment[]>([]);
 readonly availableOffset=signal(0);readonly availableTotal=signal(0);readonly offset=signal(0);readonly total=signal(0);
 readonly loading=signal(false);readonly busy=signal(false);readonly error=signal('');readonly success=signal('');
 applicationId='';evaluatorId='';
 ngOnInit(){void this.initialize();}
 async initialize(){try{await Promise.all([this.loadAvailable(),this.loadMembers(),this.load()]);}catch(e){this.error.set(apiError(e));}}
 async loadMembers(){this.members.set(await firstValueFrom(this.http.get<Evaluator[]>('/api/v1/evaluator/members')));}
 async loadAvailable(){const r=await firstValueFrom(this.http.get<Page<Assignable>>('/api/v1/evaluator/assignable-applications',{params:{limit:25,offset:this.availableOffset()}}));this.candidates.set(r.items);this.availableTotal.set(r.total);}
 async changeAvailable(n:number){this.availableOffset.update(x=>Math.max(0,x+25*n));this.applicationId='';try{await this.loadAvailable();}catch(e){this.error.set(apiError(e));}}
 async load(){this.loading.set(true);try{const r=await firstValueFrom(this.http.get<Page<Assignment>>('/api/v1/evaluator/assignments',{params:{limit:25,offset:this.offset()}}));this.assignments.set(r.items);this.total.set(r.total);}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 memberName(id:string){return this.members().find(m=>m.id===id)?.label??'Membre';}
 changePage(n:number){this.offset.update(x=>Math.max(0,x+25*n));void this.load();}
 async assign(){if(!this.applicationId||!this.evaluatorId)return;this.busy.set(true);this.error.set('');this.success.set('');try{await firstValueFrom(this.http.post('/api/v1/evaluator/assignments',{application_id:this.applicationId,evaluator_member_id:this.evaluatorId}));this.success.set('Candidature attribuée à l’évaluateur.');await this.load();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async revoke(a:Assignment){if(!confirm('Révoquer l’accès à cette candidature ?'))return;this.busy.set(true);this.error.set('');try{await firstValueFrom(this.http.post(`/api/v1/evaluator/assignments/${a.id}/revoke`,{}));this.success.set('Affectation révoquée.');await this.load();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
