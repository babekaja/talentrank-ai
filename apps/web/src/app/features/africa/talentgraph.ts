import { Component, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { TrIcon } from '../../shared/ui/tr-icon';
import { apiError } from '../../shared/recruitment';
interface Skill {id:string;code:string;label_fr:string}
interface Relation {id:string;source:string;target:string;relation_type:string;country_code:string;source_reference:string;justification:string;verification:string;effect_on_matching:string}
@Component({selector:'tr-talentgraph',standalone:true,imports:[FormsModule,TrIcon],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="brain" [size]="17"/> Innovation Africaine</p><h1>TalentGraph Africa</h1><p>Décrivez les liens entre compétences, métiers et contextes professionnels. Seules les relations vérifiées par un administrateur sont enregistrées ; aucun candidat ne reçoit automatiquement une compétence supplémentaire.</p></div></header>
<section class="grid gap-5 lg:grid-cols-[1.15fr_.85fr]">
 <div class="card p-6"><h2 class="section-heading">Explorer les relations validées</h2><p class="section-caption mt-2">Les relations « proches » ne sont pas des synonymes.</p>
 @if(busy()){<p role="status" class="mt-5 muted">Chargement des liens entre compétences…</p>}
 @if(error()){<div role="alert" class="alert-error mt-4">{{error()}}</div>}
 @if(!busy()&&!relations().length){<div class="soft-panel p-6 mt-5"><strong>Pas encore de relations vérifiées</strong><p class="section-caption mt-2">Un administrateur peut documenter la première relation et indiquer sa source.</p></div>}
 <div class="space-y-3 mt-4">@for(r of relations();track r.id){<article class="soft-panel p-4"><div class="flex flex-wrap items-start justify-between gap-3"><div><strong>{{r.source}} → {{r.target}}</strong><p class="text-xs muted mt-1">{{typeName(r.relation_type)}} · {{r.country_code}}</p></div><span class="soft-badge">Relation vérifiée</span></div><p class="text-sm mt-3">{{r.justification}}</p><p class="text-xs muted mt-2">Ne contribue jamais automatiquement au score du CV.</p><a class="inline-link text-sm mt-2" [href]="r.source_reference" rel="noopener noreferrer" target="_blank">Consulter la source ↗</a>@if(isAdmin()){<button class="btn-light mt-3 ml-3" type="button" (click)="remove(r.id)" [disabled]="saving()">Supprimer</button>}</article>}</div></div>
 <aside class="card p-6"><h2 class="section-heading">Ajouter une relation justifiée</h2><p class="section-caption mt-2">La relation est toujours approuvée par un humain. Elle ne prouve pas une expérience chez un candidat.</p>
 @if(!isAdmin()){<p class="alert-error mt-4">Création réservée à l'administrateur de votre entreprise.</p>}
 @else{<form (ngSubmit)="create()" class="space-y-4 mt-5"><label class="block"><span class="field-label">Compétence source</span><select class="field" [(ngModel)]="source" name="source" required><option value="">Choisir</option>@for(s of skills();track s.id){<option [value]="s.id">{{s.label_fr}}</option>}</select></label>
 <label class="block"><span class="field-label">Compétence liée</span><select class="field" [(ngModel)]="target" name="target" required><option value="">Choisir</option>@for(s of skills();track s.id){<option [value]="s.id">{{s.label_fr}}</option>}</select></label>
 <label class="block"><span class="field-label">Nature du lien</span><select class="field" [(ngModel)]="relationType" name="relationType"><option value="related">Compétences proches, non équivalentes</option><option value="equivalent">Équivalence validée</option><option value="prerequisite">Prérequis</option></select></label>
 <label class="block"><span class="field-label">Pays concerné</span><select class="field" [(ngModel)]="country" name="country"><option value="CD">RDC</option><option value="RW">Rwanda</option><option value="BI">Burundi</option><option value="KE">Kenya</option><option value="UG">Ouganda</option></select></label>
 <label class="block"><span class="field-label">Lien HTTPS de référence</span><input class="field" type="url" [(ngModel)]="reference" name="reference" placeholder="https://…" required/></label>
 <label class="block"><span class="field-label">Justification métier (15 caractères minimum)</span><textarea class="field" rows="4" [(ngModel)]="justification" name="justification" maxlength="2000" required></textarea></label>
 <button type="submit" class="btn-primary" [disabled]="saving()||!source||!target||source===target||justification.trim().length<15||!reference.startsWith('https://')">{{saving()?'Enregistrement…':'Valider cette relation'}}</button></form>}
 @if(message()){<p class="alert-ok mt-4" role="status">{{message()}}</p>}</aside>
</section>`})
export class TalentGraph implements OnInit {
 private http=inject(HttpClient);private auth=inject(AuthService);
 readonly skills=signal<Skill[]>([]);readonly relations=signal<Relation[]>([]);readonly busy=signal(true);readonly saving=signal(false);readonly error=signal('');readonly message=signal('');
 source='';target='';relationType='related';country='CD';reference='';justification='';
 isAdmin(){return this.auth.user()?.role==='org_admin';}
 typeName(value:string){return ({related:'Proches mais différentes',equivalent:'Équivalence documentée',prerequisite:'Prérequis'} as Record<string,string>)[value]||value;}
 ngOnInit(){void this.reload();}
 async reload(){this.busy.set(true);this.error.set('');try{const [skills,relations]=await Promise.all([firstValueFrom(this.http.get<{items:Skill[]}>('/api/v1/skills',{params:{limit:100}})),firstValueFrom(this.http.get<{items:Relation[]}>('/api/v1/africa/talentgraph/relations'))]);this.skills.set(skills.items);this.relations.set(relations.items);}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async create(){if(!this.isAdmin()||this.saving())return;this.saving.set(true);this.error.set('');this.message.set('');try{await firstValueFrom(this.http.post('/api/v1/africa/talentgraph/relations',{source_skill_id:this.source,target_skill_id:this.target,relation_type:this.relationType,justification:this.justification,source_reference:this.reference,country_code:this.country}));this.message.set('Relation validée et enregistrée. Aucun score candidat n’a été modifié.');this.justification='';await this.reload();}catch(e){this.error.set(apiError(e));}finally{this.saving.set(false);}}
 async remove(id:string){if(!this.isAdmin()||!window.confirm('Supprimer cette relation validée ?'))return;this.saving.set(true);try{await firstValueFrom(this.http.delete(`/api/v1/africa/talentgraph/relations/${encodeURIComponent(id)}`));await this.reload();}catch(e){this.error.set(apiError(e));}finally{this.saving.set(false);}}
}
