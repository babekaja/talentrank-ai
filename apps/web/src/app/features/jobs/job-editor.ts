import { Component, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { Job, Requirement, apiError } from '../../shared/recruitment';
import { LucidePlus, LucideTrash2, LucideCheckCircle2 } from '@lucide/angular';

interface SkillOption { id:string; code:string; label_fr:string; label_en:string }

@Component({selector:'tr-job-editor',standalone:true,imports:[FormsModule,RouterLink,LucidePlus,LucideTrash2,LucideCheckCircle2],template:`
<div class="mb-7"><a routerLink="/offres" class="text-sm text-indigo-700 hover:underline">← Toutes les offres</a><h1 class="mt-3 text-3xl font-bold">{{jobId() ? 'Configurer l’offre' : 'Nouvelle offre'}}</h1><p class="mt-2 text-sm text-slate-500">Les critères ne sont jamais utilisés avant confirmation humaine.</p></div>
@if(error()){<p class="alert-error mb-5" role="alert">{{error()}}</p>}@if(success()){<p class="alert-ok mb-5" role="status">{{success()}}</p>}
@if(loading()){<p>Chargement…</p>}@else {
<form class="card p-6 md:p-8" (ngSubmit)="saveJob()"><h2 class="mb-5 text-xl font-bold">1. Informations sur le poste</h2>
<div class="grid gap-4 md:grid-cols-2"><label class="md:col-span-2"><span class="field-label">Intitulé *</span><input class="field" name="title" [(ngModel)]="form.title" minlength="3" maxlength="180" required/></label>
<label><span class="field-label">Département</span><input class="field" name="department" [(ngModel)]="form.department" maxlength="120"/></label>
<label><span class="field-label">Localisation</span><input class="field" name="location" [(ngModel)]="form.location" maxlength="180"/></label>
<label><span class="field-label">Type de contrat</span><input class="field" name="contract_type" [(ngModel)]="form.contract_type"/></label>
<label><span class="field-label">Mode de travail</span><select class="field" name="work_mode" [(ngModel)]="form.work_mode"><option value="">Non précisé</option><option value="onsite">Sur site</option><option value="hybrid">Hybride</option><option value="remote">Télétravail</option></select></label>
<label><span class="field-label">Ouverture</span><input class="field" name="opens_on" type="date" [(ngModel)]="form.opens_on"/></label><label><span class="field-label">Clôture</span><input class="field" name="closes_on" type="date" [(ngModel)]="form.closes_on"/></label>
<label class="md:col-span-2"><span class="field-label">Description et missions *</span><textarea class="field min-h-34" name="description" [(ngModel)]="form.description" minlength="10" required></textarea></label></div>
<div class="mt-6 flex flex-wrap items-center gap-3"><button class="btn-primary" type="submit" [disabled]="busy() || !jobFormValid()">{{busy() ? 'Enregistrement…' : (jobId() ? 'Enregistrer les modifications' : 'Créer l’offre')}}</button>@if(job()?.criteria_confirmed_at){<span class="text-sm text-emerald-700">Critères validés. Toute modification de l'offre demande une nouvelle confirmation.</span>}</div></form>
@if(jobId()){
<section class="card mt-6 p-6 md:p-8"><div class="flex flex-wrap items-center justify-between gap-3"><div><h2 class="text-xl font-bold">2. Critères professionnels</h2><p class="mt-1 text-sm text-slate-500">Version {{job()?.criteria_version}} · {{job()?.criteria_confirmed_at ? 'Confirmée' : 'Non confirmée'}}</p></div><button type="button" (click)="addRequirement()" class="btn-light inline-flex items-center gap-2"><svg lucidePlus [size]="17"/> Ajouter un critère</button></div>
@if(unmappedSkills()>0){<p class="alert-error mt-5" role="alert">{{unmappedSkills()}} compétence(s) ne sont pas reliées au référentiel. Elles resteront en vérification humaine et ne pourront pas contribuer à la couverture documentaire.</p>}
<div class="mt-5 grid gap-4">@for(r of requirements();track $index;let idx=$index){<div class="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-950"><div class="grid gap-3 md:grid-cols-3"><label><span class="field-label">Code unique *</span><input class="field" [name]="'code'+idx" [(ngModel)]="r.code" maxlength="50"/></label><label class="md:col-span-2"><span class="field-label">Critère *</span><input class="field" [name]="'label'+idx" [(ngModel)]="r.label" maxlength="160"/></label><label><span class="field-label">Catégorie</span><select class="field" [name]="'category'+idx" [(ngModel)]="r.category" (ngModelChange)="categoryChanged(r)"><option value="skill">Compétence</option><option value="experience">Expérience</option><option value="qualification">Qualification</option><option value="certification">Certification</option><option value="language">Langue de travail</option><option value="other">Autre</option></select></label><label><span class="field-label">Poids indicatif</span><input class="field" type="number" min="1" max="100" [name]="'weight'+idx" [(ngModel)]="r.weight"/></label><label class="flex items-center gap-2 pt-7"><input type="checkbox" [name]="'required'+idx" [(ngModel)]="r.required"/> Critère essentiel</label>@if(r.category==='skill'){<label class="md:col-span-3"><span class="field-label">Compétence du référentiel</span><select class="field" [name]="'skillRef'+idx" [(ngModel)]="r.skill_ref"><option [ngValue]="null">Non reliée : vérification humaine</option>@for(s of skills();track s.id){<option [ngValue]="s.id">{{s.label_fr}} ({{s.code}})</option>}</select></label>}<label class="md:col-span-3"><span class="field-label">Justification métier *</span><textarea class="field" [name]="'why'+idx" [(ngModel)]="r.justification" rows="2" minlength="5"></textarea></label></div><button type="button" (click)="removeRequirement(idx)" class="mt-3 inline-flex items-center gap-1.5 text-sm text-red-600"><svg lucideTrash2 [size]="15"/> Supprimer ce critère</button></div>}</div>
<div class="mt-5 flex flex-wrap gap-3"><button class="btn-primary" type="button" [disabled]="busy() || !requirementsValid()" (click)="saveRequirements()">Enregistrer les critères</button><button class="btn-light inline-flex items-center gap-2" type="button" [disabled]="busy() || !!job()?.criteria_confirmed_at || job()?.criteria_version === 0" (click)="confirm()"><svg lucideCheckCircle2 [size]="17"/> Confirmer cette version</button></div>
<p class="mt-4 text-sm text-slate-500">Modifier les critères crée une nouvelle version et annule la confirmation. Une campagne active verrouille cette configuration.</p></section>
}
}`})
export class JobEditor implements OnInit {
 private readonly http=inject(HttpClient); private readonly route=inject(ActivatedRoute); private readonly router=inject(Router);
 readonly jobId=signal<string|null>(null);readonly job=signal<Job|null>(null);readonly requirements=signal<Requirement[]>([]);readonly skills=signal<SkillOption[]>([]);
 readonly busy=signal(false);readonly loading=signal(false);readonly error=signal('');readonly success=signal('');
 private baseline='';
 form={title:'',department:'',location:'',contract_type:'',work_mode:'',description:'',opens_on:'',closes_on:''};
 ngOnInit(){this.baseline=this.snapshot();void this.loadSkills();const id=this.route.snapshot.paramMap.get('id');if(id){this.jobId.set(id);void this.load();}}
 async loadSkills(){try{const data=await firstValueFrom(this.http.get<{items:SkillOption[]}>('/api/v1/skills?limit=100'));this.skills.set(data.items);}catch(e){this.error.set(apiError(e));}}
 private show(row:Job){this.job.set(row);this.requirements.set(row.requirements.map(v=>({...v,skill_ref:v.skill_ref??v.resolved_skill_id??null})));this.form={title:row.title,department:row.department||'',location:row.location||'',contract_type:row.contract_type||'',work_mode:row.work_mode||'',description:row.description,opens_on:row.opens_on||'',closes_on:row.closes_on||''};this.baseline=this.snapshot();}
 async load(){this.loading.set(true);try{this.show(await firstValueFrom(this.http.get<Job>(`/api/v1/jobs/${this.jobId()}`)));}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 private snapshot(){return JSON.stringify({form:this.form,requirements:this.requirements().map(r=>({code:r.code,label:r.label,category:r.category,required:r.required,weight:r.weight,justification:r.justification,skill_ref:r.skill_ref}))});}
 canLeave(){return this.snapshot()===this.baseline || window.confirm('Vous avez des modifications non enregistrées. Quitter cette page sans les sauvegarder ?');}
 private payload(){return {...this.form,department:this.form.department||null,location:this.form.location||null,contract_type:this.form.contract_type||null,work_mode:this.form.work_mode||null,opens_on:this.form.opens_on||null,closes_on:this.form.closes_on||null};}
 jobFormValid(){return this.form.title.trim().length>=3 && this.form.description.trim().length>=10 && (!this.form.closes_on||!this.form.opens_on||this.form.closes_on>=this.form.opens_on);}
 requirementsValid(){const req=this.requirements();return req.length>0 && new Set(req.map(r=>r.code.trim())).size===req.length && req.every(r=>r.code.trim().length>0&&r.label.trim().length>0&&r.justification.trim().length>=5&&r.weight>=1&&r.weight<=100);}
 async saveJob(){if(!this.jobFormValid())return;this.busy.set(true);this.error.set('');this.success.set('');try{
  const p=this.payload();const row=await firstValueFrom(this.jobId()?this.http.patch<Job>(`/api/v1/jobs/${this.jobId()}`,p):this.http.post<Job>('/api/v1/jobs',p));this.show(row);
  if(!this.jobId()){this.jobId.set(row.id);await this.router.navigate(['/offres',row.id],{replaceUrl:true});}
  this.success.set('Offre enregistrée.');
 }catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 addRequirement(){this.requirements.update(v=>[...v,{code:'',label:'',category:'skill',required:true,weight:1,justification:'',skill_ref:null}]);}
 categoryChanged(requirement:Requirement){if(requirement.category!=='skill')requirement.skill_ref=null;}
 unmappedSkills(){return this.requirements().filter(r=>r.category==='skill'&&!r.skill_ref).length;}
 removeRequirement(index:number){this.requirements.update(v=>v.filter((_,i)=>i!==index));}
 async saveRequirements(){if(!this.requirementsValid())return;this.busy.set(true);this.error.set('');this.success.set('');try{
  const row=await firstValueFrom(this.http.put<Job>(`/api/v1/jobs/${this.jobId()}/requirements`,{items:this.requirements().map(({id,...data})=>data)}));this.show(row);this.success.set('Critères enregistrés. Confirmez cette version après vérification.');
 }catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async confirm(){this.busy.set(true);this.error.set('');this.success.set('');try{const row=await firstValueFrom(this.http.post<Job>(`/api/v1/jobs/${this.jobId()}/requirements/confirm`,{expected_version:this.job()?.criteria_version}));this.show(row);this.success.set('Critères confirmés : une campagne peut être créée.');}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
