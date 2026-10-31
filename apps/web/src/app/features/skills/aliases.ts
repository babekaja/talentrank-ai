import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, computed, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { apiError } from '../../shared/recruitment';
import { EmptyState } from '../../shared/ui/empty-state';
interface Alias {id:string;alias:string;source:string;justification?:string}
@Component({selector:'tr-skill-aliases',standalone:true,imports:[TrIcon,RouterLink,EmptyState],template:`
<a class="inline-link text-sm" routerLink="/competences">← Retour aux compétences</a>
<header class="page-intro mt-5"><div><p class="eyebrow"><tr-icon name="book" [size]="15"/> Différentes façons de nommer une compétence</p><h1>Synonymes et variantes</h1><p>Une variante doit désigner exactement la même compétence. Une technologie voisine ou un diplôme différent ne sont pas des synonymes.</p></div></header>
@if(error()){<div class="alert-error mb-5" role="alert">{{error()}} <button class="underline ml-2" type="button" (click)="load()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Réessayer</button></div>}
@if(info()){<div class="alert-ok mb-5" role="status">{{info()}}</div>}
<div class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,.85fr)]">
<section class="card p-6"><h2 class="section-heading">Variantes connues</h2><p class="section-caption mt-1">Expressions vérifiées dans le référentiel ou ajoutées pour votre entreprise.</p><div class="mt-4 flex flex-wrap gap-2"><span class="soft-badge">{{officialCount()}} référentiel</span><span class="soft-badge">{{localCount()}} locales</span></div>
@if(loading()){<p class="mt-7 muted" role="status">Chargement des synonymes…</p>}
@else if(!aliases().length){<tr-empty-state title="Aucune variante enregistrée" description="Une nouvelle expression ne sera reconnue comme synonyme qu'après validation par un administrateur."/>}
@else{<div class="mt-5 space-y-3">@for(a of aliases();track a.id){<article class="rounded-xl border border-slate-200 dark:border-slate-700 p-4"><div class="flex flex-wrap items-center justify-between gap-2"><strong>{{a.alias}}</strong><span class="soft-badge">{{a.source==='organization'?'Votre entreprise':'Référentiel'}}</span></div>@if(a.justification){<p class="mt-2 section-caption">{{a.justification}}</p>}</article>}</div>}
</section>
<section class="card p-6"><h2 class="section-heading">Ajouter une variante locale</h2><p class="section-caption mt-2">Cette action modifie les règles de reconnaissance pour votre organisation. Elle est réservée aux administrateurs.</p>
@if(canEdit()) {<form class="mt-5 space-y-4" (submit)="submit($event)"><label class="block"><span class="field-label">Expression exacte</span><input class="field" [value]="alias()" (input)="alias.set($any($event.target).value)" maxlength="190" placeholder="Ex. gestion des inventaires" required/><span class="block mt-1 text-xs muted">Évitez les formulations trop larges.</span></label>
<label class="block"><span class="field-label">Langue de la variante</span><select class="field" [value]="language()" (change)="language.set($any($event.target).value)"><option value="fr">Français</option><option value="en">Anglais</option><option value="und">Non définie</option></select></label>
<label class="block"><span class="field-label">Justification professionnelle</span><textarea class="field" rows="4" maxlength="400" [value]="reason()" (input)="reason.set($any($event.target).value)" placeholder="Pourquoi cette expression désigne-t-elle exactement la même compétence ?" required></textarea><span class="block mt-1 text-xs muted">Au moins 8 caractères ; la justification reste auditée.</span></label>
<div class="soft-panel p-4 text-xs leading-relaxed muted">Vérifiez l'équivalence avant de confirmer. Une simple ressemblance sémantique ne suffit pas.</div><button class="btn-primary w-full" type="submit" [disabled]="busy()||alias().trim().length<2||reason().trim().length<8">{{busy()?'Enregistrement…':'Valider et enregistrer la variante'}}</button></form>}
@else{<div class="soft-panel p-5 mt-5"><p class="font-semibold">Consultation seulement</p><p class="section-caption mt-2">Contactez l'administrateur de votre entreprise pour proposer une variante.</p></div>}
</section></div>`})
export class SkillAliases implements OnInit {
 private readonly http=inject(HttpClient);private readonly route=inject(ActivatedRoute);private readonly auth=inject(AuthService);
 private get id(){return this.route.snapshot.paramMap.get('id')??'';}
 readonly alias=signal('');readonly reason=signal('');readonly language=signal('fr');readonly aliases=signal<Alias[]>([]);
 readonly loading=signal(true);readonly busy=signal(false);readonly error=signal('');readonly info=signal('');
 readonly canEdit=computed(()=>this.auth.user()?.role==='org_admin');
 readonly officialCount=computed(()=>this.aliases().filter(a=>a.source!=='organization').length);
 readonly localCount=computed(()=>this.aliases().filter(a=>a.source==='organization').length);
 ngOnInit(){void this.load();}
 submit(e:Event){e.preventDefault();void this.add();}
 async load(){this.loading.set(true);this.error.set('');try{const response=await firstValueFrom(this.http.get<{items:Alias[]}>(`/api/v1/skills/${encodeURIComponent(this.id)}/aliases`));this.aliases.set(response.items);}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 async add(){if(!this.canEdit()||this.busy()||this.alias().trim().length<2||this.reason().trim().length<8)return;this.busy.set(true);this.error.set('');this.info.set('');try{await firstValueFrom(this.http.post(`/api/v1/skills/${encodeURIComponent(this.id)}/aliases`,{alias:this.alias().trim(),justification:this.reason().trim(),language:this.language()}));this.alias.set('');this.reason.set('');await this.load();this.info.set('Variante ajoutée au référentiel local. Cette validation est historisée.');}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
