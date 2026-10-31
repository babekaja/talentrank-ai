import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { apiError, Page } from '../../shared/recruitment';
import { AuthService } from '../../core/auth/auth.service';

interface Course {id:string;title:string;provider:string;official_url:string;language:string;level:string;skill_id:string|null;description:string;verified_at:string|null}
interface Skill {id:string;label_fr:string;code:string}
interface CourseBody {title:string;provider:string;official_url:string;language:string;level:string;skill_id:string|null;description:string}
const emptyForm=():CourseBody=>({title:'',provider:'',official_url:'',language:'fr',level:'débutant',skill_id:null,description:''});
@Component({selector:'tr-training',standalone:true,imports:[TrIcon,FormsModule],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="graduation" [size]="15"/> Apprentissage et développement</p><h1 class="mt-2">Catalogue des formations</h1><p>Réunissez des programmes vérifiables pour aider les personnes à développer leurs compétences. Les formations ne sont jamais inventées.</p></div></header>
@if(error()){<p class="alert-error mb-4" role="alert">{{error()}}</p>}@if(success()){<p class="alert-ok mb-4" role="status">{{success()}}</p>}
<section class="card p-5 mb-6"><form class="flex flex-wrap items-end gap-3" (ngSubmit)="applySearch()"><label class="min-w-0 flex-1"><span class="field-label">Rechercher une formation</span><input type="search" class="field" [(ngModel)]="search" name="q" placeholder="Python, gestion des stocks…"/></label><button type="submit" class="btn-light"><tr-icon name="search" [size]="16" class="inline-flex align-middle mr-1"/>Rechercher</button><button type="button" class="btn-light" (click)="resetSearch()">Réinitialiser</button></form></section>
<section class="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
<div><div class="flex items-center justify-between mb-3"><h2 class="text-lg font-bold">Formations enregistrées ({{total()}})</h2><button type="button" class="btn-light" [disabled]="loading()" (click)="load()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Actualiser</button></div>
@if(loading()){<p role="status">Chargement…</p>}@else if(!rows().length){<div class="card p-7"><h3 class="font-semibold">Le catalogue est encore vide</h3><p class="section-caption mt-2">Ajoutez votre premier programme depuis le formulaire, avec le lien de son organisme.</p></div>}
@else{<div class="space-y-3">@for(c of rows();track c.id){<article class="card p-5"><div class="flex justify-between gap-4 items-start"><div><h3 class="font-bold">{{c.title}}</h3><p class="mt-1 text-sm text-slate-500">{{c.provider}} · {{c.language}} · {{c.level}}</p></div><span class="text-xs font-semibold" [class.text-emerald-700]="!!c.verified_at" [class.text-amber-700]="!c.verified_at">{{c.verified_at?'Lien vérifié par votre équipe':'Lien à vérifier'}}</span></div>
<p class="mt-3 text-sm whitespace-pre-wrap">{{c.description}}</p>
<div class="mt-3 flex flex-wrap gap-3 items-center"><a class="text-indigo-700 underline text-sm" [href]="c.official_url" target="_blank" rel="noopener noreferrer">Consulter la source <tr-icon name="external" [size]="16"/></a><button type="button" class="btn-light" (click)="edit(c)">Modifier</button>@if(!c.verified_at && auth.user()?.role==='org_admin'){<button type="button" class="btn-light" [disabled]="busy()" (click)="verify(c)">Source vérifiée</button>}<button type="button" class="text-rose-700 underline text-sm" [disabled]="busy()" (click)="archive(c)">Archiver</button></div>
</article>}</div>}
<div class="flex justify-between items-center p-4"><small class="text-slate-500">{{total()}} formation(s)</small><div class="flex gap-2"><button class="btn-light" [disabled]="offset()===0" (click)="page(-1)">Précédent</button><button class="btn-light" [disabled]="offset()+25>=total()" (click)="page(1)"><tr-icon name="arrow-right" [size]="16" class="inline-flex align-middle mr-1"/>Suivant</button></div></div></div>
<form class="card p-6 self-start" (ngSubmit)="save()"><div class="flex justify-between items-center mb-5"><h2 class="font-bold text-lg">{{editingId()?'Modifier la fiche':'Nouvelle formation'}}</h2>@if(editingId()){<button type="button" class="btn-light" (click)="clear()">Annuler</button>}</div>
<div class="space-y-3"><label class="block"><span class="field-label">Titre du programme</span><input class="field" name="title" [(ngModel)]="form.title" required minlength="3" maxlength="220"/></label>
<label class="block"><span class="field-label">Organisme proposant le cours</span><input class="field" name="provider" [(ngModel)]="form.provider" required maxlength="180"/></label>
<label class="block"><span class="field-label">Lien officiel (http ou https)</span><input class="field" name="url" [(ngModel)]="form.official_url" required type="url" placeholder="https://…"/></label>
<div class="grid grid-cols-2 gap-3"><label><span class="field-label">Langue</span><select class="field" name="language" [(ngModel)]="form.language"><option value="fr">Français</option><option value="en">Anglais</option><option value="sw">Swahili</option><option value="rw">Kinyarwanda</option></select></label><label><span class="field-label">Niveau</span><select class="field" name="level" [(ngModel)]="form.level"><option value="débutant">Débutant</option><option value="intermédiaire">Intermédiaire</option><option value="avancé">Avancé</option></select></label></div>
<label class="block"><span class="field-label">Compétence associée (facultatif)</span><select class="field" name="skill" [(ngModel)]="form.skill_id"><option [ngValue]="null">Aucune</option>@for(s of skills();track s.id){<option [ngValue]="s.id">{{s.label_fr}}</option>}</select><span class="text-xs text-slate-500">Choix limité aux premiers concepts chargés, sans inférer de nouvelles compétences.</span></label>
<label class="block"><span class="field-label">Description factuelle</span><textarea class="field" rows="4" name="description" [(ngModel)]="form.description" maxlength="3000" placeholder="Public cible, prérequis et contenu confirmés par l'organisme"></textarea></label>
<button type="submit" class="btn-primary" [disabled]="busy() || !form.title.trim() || !form.provider.trim() || !isWebUrl()">{{busy()?'Enregistrement…':editingId()?'Enregistrer les changements':'Ajouter cette formation'}}</button></div>
<p class="mt-4 text-xs text-slate-500">L'ajout ne certifie pas la source. Seul un administrateur peut dater une vérification explicite, après consultation du site.</p>
</form></section>
`})
export class TrainingPage implements OnInit {
 private http=inject(HttpClient);readonly auth=inject(AuthService);
 readonly rows=signal<Course[]>([]);readonly skills=signal<Skill[]>([]);readonly total=signal(0);readonly offset=signal(0);readonly appliedSearch=signal('');
 readonly loading=signal(false);readonly busy=signal(false);readonly error=signal('');readonly success=signal('');readonly editingId=signal('');
 search='';form:CourseBody=emptyForm();
 ngOnInit(){void this.load();void this.loadSkills();}
 async load(){this.loading.set(true);this.error.set('');try{const r=await firstValueFrom(this.http.get<Page<Course>>('/api/v1/training-courses',{params:{limit:25,offset:this.offset(),q:this.appliedSearch()}}));this.rows.set(r.items);this.total.set(r.total);}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 async loadSkills(){try{const r=await firstValueFrom(this.http.get<{items:Skill[]}>('/api/v1/skills',{params:{limit:100}}));this.skills.set(r.items);}catch(e){this.error.set(apiError(e));}}
 applySearch(){this.offset.set(0);this.appliedSearch.set(this.search.trim());void this.load();}
 resetSearch(){this.search='';this.applySearch();}
 page(delta:number){this.offset.update(x=>Math.max(0,x+25*delta));void this.load();}
 clear(){this.editingId.set('');this.form=emptyForm();}
 edit(c:Course){this.editingId.set(c.id);this.form={title:c.title,provider:c.provider,official_url:c.official_url,language:c.language,level:c.level,description:c.description,skill_id:c.skill_id};this.success.set('');}
 isWebUrl(){return /^https?:\/\/[a-z0-9][^\s]*$/i.test(this.form.official_url);}
 async save(){if(this.busy()||!this.isWebUrl())return;this.busy.set(true);this.error.set('');this.success.set('');try{const id=this.editingId();if(id)await firstValueFrom(this.http.put(`/api/v1/training-courses/${id}`,this.form));else await firstValueFrom(this.http.post('/api/v1/training-courses',this.form));this.success.set(id?'Fiche actualisée : la validation antérieure du lien a été annulée.':'Formation créée : lien non vérifié.');this.clear();await this.load();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async verify(c:Course){if(this.auth.user()?.role!=='org_admin')return;if(!confirm('Avez-vous consulté la source officielle de cette formation et vérifié son existence ?'))return;this.busy.set(true);this.error.set('');try{await firstValueFrom(this.http.post(`/api/v1/training-courses/${c.id}/verify`,{source_checked:true}));this.success.set('Vérification humaine enregistrée avec date et identité.');await this.load();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async archive(c:Course){if(!confirm('Archiver cette formation dans le catalogue de votre entreprise ?'))return;this.busy.set(true);this.error.set('');try{await firstValueFrom(this.http.delete(`/api/v1/training-courses/${c.id}`));this.success.set('Formation archivée.');if(this.editingId()===c.id)this.clear();await this.load();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
