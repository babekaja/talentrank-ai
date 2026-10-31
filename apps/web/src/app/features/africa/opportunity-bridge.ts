import {Component,inject,OnInit,signal} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {ActivatedRoute,RouterLink} from '@angular/router';
import {firstValueFrom} from 'rxjs';
import {TrIcon} from '../../shared/ui/tr-icon';
import {apiError} from '../../shared/recruitment';
interface Course{title:string;provider:string;official_url:string;language:string;level:string;skill_id:string;source_verified_at:string}
interface Response{status:string;items:Course[];note?:string}
@Component({selector:'tr-africa-opportunity',standalone:true,imports:[TrIcon,RouterLink],template:`
<a routerLink="/matching" class="inline-link">← Retour aux analyses</a>
<header class="page-intro mt-4"><div><p class="eyebrow"><tr-icon name="graduation-cap" [size]="17"/> Opportunity Bridge Africa</p><h1>Des pistes de développement professionnel</h1><p>Une formation peut aider à préparer une compétence à l'avenir. Le système n'affirme jamais qu'un CV incomplet signifie une absence de capacité.</p></div></header>
@if(error()){<div role="alert" class="alert-error mb-5">{{error()}}</div>}
@if(busy()){<div class="card p-6" role="status">Vérification du consentement et des formations disponibles…</div>}
@if(data();as d){
@if(d.status==='consent_not_recorded'){<div class="card p-7"><h2 class="section-heading">Partage non autorisé</h2><p class="section-caption mt-3">Aucun parcours individualisé n'est affiché. L'organisation doit d'abord documenter un accord explicite du candidat ; la déclaration administrative seule ne vaut pas consentement indépendant.</p></div>}
@else if(!d.items.length){<div class="card p-7"><h2 class="section-heading">Aucune formation vérifiée proposée</h2><p class="section-caption mt-3">Le catalogue ne dispose pas d'une formation validée couvrant les critères concernés. Aucun lien ou certificat n'a été inventé.</p></div>}
@else{<div class="grid gap-4 lg:grid-cols-2">@for(c of d.items;track c.official_url){<article class="card p-6"><p class="eyebrow">Source vérifiée humainement</p><h2 class="section-heading mt-2">{{c.title}}</h2><p class="section-caption mt-2">{{c.provider}} · {{c.language}} · {{c.level}}</p><a class="btn-light mt-5" [href]="c.official_url" rel="noopener noreferrer" target="_blank">Voir le site officiel ↗</a></article>}</div>}
<p class="section-caption mt-5">{{d.note}}</p>}
`})
export class OpportunityBridge implements OnInit {
 private http=inject(HttpClient);private route=inject(ActivatedRoute);
 readonly data=signal<Response|null>(null);readonly error=signal('');readonly busy=signal(true);
 ngOnInit(){void this.load();}
 async load(){this.busy.set(true);this.error.set('');const id=this.route.snapshot.paramMap.get('id')??'';try{this.data.set(await firstValueFrom(this.http.get<Response>(`/api/v1/africa/opportunities/matching-results/${encodeURIComponent(id)}`)));}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
