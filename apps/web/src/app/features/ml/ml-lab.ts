import { VisualGuide } from '../../shared/ui/visual-guide';
import { TrIcon } from '../../shared/ui/tr-icon';
import {Component, inject, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {HttpClient} from '@angular/common/http';
import {firstValueFrom} from 'rxjs';
import {apiError} from '../../shared/recruitment';

interface Suggestion {
  skill_id: string;
  code: string;
  label: string;
  similarity: number;
  status: string;
}
interface SuggestionsResponse {items: Suggestion[]; model?: string; note?: string}

@Component({
  selector:'tr-ml-lab', standalone:true, imports:[VisualGuide, TrIcon,FormsModule],
  template:`
  <header class="page-intro"><div><p class="eyebrow"><tr-icon name="brain" [size]="15"/> Espace expérimental · Personnel habilité</p><h1 class="mt-2">Tester la recherche intelligente</h1><p>Comparez des formulations professionnelles en français et en anglais. Les suggestions sont des pistes de vérification : elles ne modifient pas les candidatures.</p></div></header>
<tr-visual-guide title="Portée des essais" description="Les essais en français et en anglais ne constituent pas des résultats validés sur les candidats." />
  <section class="card p-5 mb-5">
    <label class="block text-sm font-medium mb-2" for="ml-query">Formulation professionnelle à rapprocher</label>
    <textarea id="ml-query" name="ml-query" class="field" rows="3"
      placeholder="Ex. : Conception et maintenance de services REST avec FastAPI"
      [ngModel]="query()" (ngModelChange)="query.set($event)" maxlength="250"></textarea>
    <div class="flex flex-wrap items-center justify-between gap-3 mt-4">
      <p class="text-xs text-slate-500">Les résultats sont des pistes de vérification et non des compétences acquises.</p>
      <button class="btn-primary" [disabled]="busy() || query().trim().length < 2" (click)="search()">
        {{busy() ? 'Analyse…' : 'Proposer des rapprochements'}}
      </button>
    </div>
  </section>
  @if(error()) {<div role="alert" class="alert-error mb-4">{{error()}}</div>}
  @if(result(); as r) {
    <p class="mb-4 text-xs text-slate-500">Modèle local : {{r.model || 'non communiqué'}} · Similarité cosinus brute, pas un pourcentage d'expertise.</p>
    @if(r.items.length === 0) {<div class="card p-5">Aucune suggestion disponible.</div>}
    @for(item of r.items; track item.skill_id) {
      <article class="card p-4 mb-3 flex items-center justify-between gap-3">
        <div><h2 class="font-semibold">{{item.label}}</h2>
          <p class="text-sm text-slate-500">{{item.code}} · à vérifier par un recruteur</p></div>
        <div class="text-right"><p class="font-semibold tabular-nums">{{item.similarity.toFixed(3)}}</p>
          <small class="text-slate-500">cosinus</small></div>
      </article>
    }
  }
  `
})
export class MlLab {
  private readonly http=inject(HttpClient);
  readonly query=signal('');
  readonly result=signal<SuggestionsResponse|null>(null);
  readonly error=signal('');
  readonly busy=signal(false);
  async search(){
    this.error.set('');this.busy.set(true);this.result.set(null);
    try{this.result.set(await firstValueFrom(this.http.post<SuggestionsResponse>(
      '/api/v1/skills/semantic-suggestions',{text:this.query().trim(),limit:8})));}
    catch(e){this.error.set(apiError(e));}
    finally{this.busy.set(false)}
  }
}
