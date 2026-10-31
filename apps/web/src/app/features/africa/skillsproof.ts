import { Component, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { TrIcon } from '../../shared/ui/tr-icon';
import { apiError } from '../../shared/recruitment';
interface Mention {evidence_id:string;skill:string;status:string;page_number:number;start_offset:number;end_offset:number;text:string;matched_text:string;method:string;rules_version:string}
@Component({selector:'tr-africa-skillsproof',standalone:true,imports:[TrIcon,RouterLink],template:`
<a routerLink="/importations" class="inline-link text-sm">← Retour aux CV</a>
<header class="page-intro mt-4"><div><p class="eyebrow"><tr-icon name="file-search" [size]="17"/> SkillsProof AI</p><h1>Preuves dans le document</h1><p>Chaque mention renvoie à une page et à un passage exact du CV. Une mention n'atteste pas automatiquement un niveau d'expertise.</p></div><button type="button" class="btn-light" (click)="load()" [disabled]="busy()">Actualiser</button></header>
@if(error()){<div class="alert-error mb-5" role="alert">{{error()}}</div>}
@if(busy()){<div role="status" class="card p-6">Consultation des preuves et vérification de leurs positions…</div>}
@else if(!rows().length){<div class="card p-8"><h2 class="section-heading">Aucune mention vérifiable</h2><p class="section-caption mt-3">Le traitement NLP peut être incomplet, ou le CV ne contient aucune occurrence enregistrée. Cela ne signifie pas que le candidat ne possède pas de compétences.</p></div>}
@else{<div class="grid gap-4 lg:grid-cols-2">@for(r of rows();track r.evidence_id){<article class="card p-5"><div class="flex flex-wrap justify-between gap-2"><strong>{{r.skill}}</strong><span class="soft-badge">{{statusLabel(r.status)}}</span></div><p class="text-xs muted mt-2">CV · page {{r.page_number}} · méthode {{r.method}}</p><blockquote class="soft-panel p-4 mt-3 text-sm leading-relaxed break-words">{{r.text}}</blockquote><a class="btn-light mt-4" [routerLink]="['/documents',id,'visionneuse']" [queryParams]="{page:r.page_number,start:r.start_offset,end:r.end_offset}">Ouvrir la preuve dans le CV</a></article>}</div>}
<p class="section-caption mt-5">La reconnaissance de termes et la vérification des qualifications professionnelles sont deux opérations différentes.</p>`})
export class SkillsProof implements OnInit {
 private http=inject(HttpClient);private route=inject(ActivatedRoute);
 readonly rows=signal<Mention[]>([]);readonly busy=signal(true);readonly error=signal('');
 get id(){return this.route.snapshot.paramMap.get('id')??'';}
 ngOnInit(){void this.load();}
 statusLabel(v:string){return ({human_confirmed:'Mention confirmée par un humain',human_rejected:'Mention rejetée',requires_review:'À vérifier',direct_mention_not_skill_level:'Mention observée'} as Record<string,string>)[v]??'Mention';}
 async load(){this.busy.set(true);this.error.set('');try{const r=await firstValueFrom(this.http.get<{items:Mention[]}>(`/api/v1/africa/skillsproof/documents/${encodeURIComponent(this.id)}`));this.rows.set(r.items);}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
