import { HumanStatus } from '../../shared/ui/human-status';
import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { Page, apiError } from '../../shared/recruitment';

interface Assignment {
  id:string;application_id:string;candidate_reference:string;campaign_name:string;
  status:'assigned'|'completed'|'revoked';created_at:string;completed_at:string|null;
}
interface Evidence {page_number:number;excerpt:string;status:string;context_code:string;skill_id:string}

@Component({selector:'tr-my-reviews',standalone:true,imports:[HumanStatus,TrIcon,FormsModule],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="clipboard" [size]="15"/> Votre espace d’évaluation</p><h1 class="mt-2">Dossiers à examiner</h1><p>Concentrez-vous sur les réalisations documentées. Vous ne voyez que les candidatures confiées à votre équipe.</p></div></header><div class="human-callout mb-6 p-4 text-sm leading-relaxed"><strong>Votre rôle compte.</strong> Vérifiez les extraits, consignez vos questions et indiquez ce qui mérite une discussion. Les suggestions informatiques ne remplacent jamais votre appréciation.</div>
@if(error()){<p class="alert-error mb-4" role="alert">{{error()}}</p>}
@if(success()){<p class="alert-ok mb-4" role="status">{{success()}}</p>}
<div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
<section class="card overflow-hidden" aria-label="Affectations">
 <div class="flex justify-between items-center gap-3 border-b border-slate-100 p-5 dark:border-slate-800"><h2 class="font-bold">Dossiers ({{total()}})</h2><button type="button" class="btn-light" [disabled]="loading()" (click)="load()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Actualiser</button></div>
 @if(loading()){<p class="p-5" role="status">Chargement des affectations…</p>}
 @else if(!rows().length){<div class="p-7 text-center"><h3 class="font-semibold">Vous êtes à jour</h3><p class="section-caption mt-2">Aucun nouveau dossier ne vous a été attribué. Les prochaines affectations apparaîtront ici.</p></div>}
 @else{<div class="divide-y divide-slate-100 dark:divide-slate-800">@for(a of rows();track a.id){<button type="button" class="block w-full p-5 text-left hover:bg-slate-50 dark:hover:bg-slate-800" [attr.aria-pressed]="selected()?.id===a.id" (click)="open(a)"><span class="block font-semibold">{{a.candidate_reference}}</span><span class="block text-xs text-slate-500 mt-1">{{a.campaign_name}} · {{a.status==='assigned'?'À examiner':'Avis enregistré'}}</span></button>}</div>}
 <div class="flex items-center justify-between p-4"><span class="text-xs text-slate-500">{{total()}} dossier(s)</span><div class="flex gap-2"><button type="button" class="btn-light" [disabled]="offset()===0 || loading()" (click)="page(-1)">Précédent</button><button type="button" class="btn-light" [disabled]="offset()+25>=total() || loading()" (click)="page(1)"><tr-icon name="arrow-right" [size]="16" class="inline-flex align-middle mr-1"/>Suivant</button></div></div>
</section>
<section class="card p-6" aria-label="Examen du dossier">
 @if(!selected()){<h2 class="section-heading">Choisissez un dossier pour commencer</h2><p class="section-caption mt-3">À gauche, sélectionnez une référence. Vous pourrez consulter les passages pertinents et rédiger votre avis en gardant une trace des faits observés.</p>}
 @else{<div class="flex justify-between gap-3"><div><p class="eyebrow">Référence masquée</p><h2 class="text-xl font-bold">{{selected()!.candidate_reference}}</h2><p class="text-xs text-slate-500 mt-1">{{selected()!.campaign_name}}</p></div><button type="button" class="btn-light self-start" (click)="close()"><tr-icon name="x" [size]="16" class="inline-flex align-middle mr-1"/>Fermer</button></div>
  <div class="mt-6"><h3 class="font-bold">Ce qui est écrit dans le CV</h3><p class="text-xs text-slate-500 mt-1">Ces phrases proviennent du document. Lisez-les dans leur contexte avant de donner votre avis.</p>
  @if(evidenceLoading()){<p class="mt-3" role="status">Lecture des mentions…</p>}
  @else if(!evidence().length){<p class="mt-3 text-sm text-slate-500">Aucune mention exploitable. Ne déduisez pas l'absence de compétence.</p>}
  @else{<ul class="mt-3 space-y-2">@for(e of evidence();track $index){<li class="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700"><strong>Page {{e.page_number}}</strong> · {{e.excerpt}}<p class="text-xs text-slate-500">{{e.status | humanStatus:'mention'}}<details class="mt-2 text-xs muted"><summary class="cursor-pointer">Informations techniques</summary><p class="mt-2">Contexte : {{e.context_code}}</p></details></p></li>}</ul>}
  </div>
  @if(selected()!.status==='assigned'){<form class="mt-6 space-y-3 border-t border-slate-200 pt-5 dark:border-slate-700" (ngSubmit)="submit()">
   <h3 class="font-bold">Votre avis sur ce dossier</h3><p class="section-caption">Rédigez un retour utile pour les collègues qui reprendront le dossier.</p><label class="block"><span class="field-label">Conclusion</span><select name="finding" class="field" [(ngModel)]="finding"><option value="reviewed">Examen terminé</option><option value="needs_clarification">Vérification nécessaire</option><option value="shortlisted">À proposer à l'équipe de recrutement</option></select></label>
   <label class="block"><span class="field-label">Expliquez votre avis</span><textarea class="field" name="note" [(ngModel)]="note" required minlength="3" maxlength="4000" rows="5" placeholder="Par exemple : le CV décrit un projet Angular en page 2, mais les dates de réalisation restent à confirmer…"></textarea></label>
   <button class="btn-primary" type="submit" [disabled]="busy() || note.trim().length<3">{{busy()?'Enregistrement…':'Valider mon avis'}}</button><p class="text-xs text-slate-500">Votre avis sera enregistré dans l’historique et ne prendra aucune décision d’embauche à la place de l’équipe.</p>
  </form>}@else{<p class="alert-ok mt-5" role="status">Avis enregistré. Le dossier ne peut plus être modifié depuis cet espace.</p>}
 }
</section></div>
`})
export class MyReviews implements OnInit {
 private http=inject(HttpClient);
 readonly rows=signal<Assignment[]>([]);readonly selected=signal<Assignment|null>(null);
 readonly evidence=signal<Evidence[]>([]);readonly loading=signal(false);readonly evidenceLoading=signal(false);
 readonly busy=signal(false);readonly error=signal('');readonly success=signal('');
 readonly offset=signal(0);readonly total=signal(0);
 finding:'reviewed'|'needs_clarification'|'shortlisted'='reviewed';note='';
 ngOnInit(){void this.load();}
 async load(){this.loading.set(true);this.error.set('');try{const r=await firstValueFrom(this.http.get<Page<Assignment>>('/api/v1/evaluator/assignments',{params:{limit:25,offset:this.offset()}}));this.rows.set(r.items);this.total.set(r.total);const selected=this.selected();if(selected){this.selected.set(r.items.find(x=>x.id===selected.id)??null);}}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 page(step:number){this.offset.update(x=>Math.max(0,x+25*step));this.close();void this.load();}
 close(){this.selected.set(null);this.evidence.set([]);this.note='';}
 async open(a:Assignment){this.selected.set(a);this.note='';this.evidence.set([]);this.error.set('');this.evidenceLoading.set(true);try{const r=await firstValueFrom(this.http.get<{items:Evidence[]}>(`/api/v1/evaluator/assignments/${a.id}/evidence`));if(this.selected()?.id===a.id)this.evidence.set(r.items);}catch(e){this.error.set(apiError(e));}finally{this.evidenceLoading.set(false);}}
 async submit(){const a=this.selected();if(!a || !this.note.trim() || this.busy())return;this.busy.set(true);this.error.set('');this.success.set('');try{await firstValueFrom(this.http.post(`/api/v1/evaluator/assignments/${a.id}/reviews`,{finding:this.finding,note:this.note.trim()}));this.success.set('Votre avis humain a été enregistré.');this.note='';await this.load();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
