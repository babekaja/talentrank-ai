import { VisualGuide } from '../../shared/ui/visual-guide';
import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { apiError } from '../../shared/recruitment';

type Policy = { retention_days: number; configured: boolean; automatic_deletion: boolean };
type Due = { id: string; reference: string; created_at: string; documents: number };
type Preview = { applications: number; documents: number; analyses_impactees: number; legal_hold: boolean; warning: string };

@Component({selector:'tr-privacy', standalone:true, imports:[VisualGuide, TrIcon,FormsModule], template:`
<section class="space-y-6">
  <header><h1 class="text-3xl font-bold"><tr-icon name="lock" [size]="23" class="inline-flex align-middle mr-2"/> Confidentialité et conservation</h1>
  <p class="mt-2 text-sm text-slate-500">Administration des délais et demandes de suppression. Aucune suppression automatique n'est activée.</p></header>
<tr-visual-guide title="Accès et conservation des documents" description="Les documents restent privés ; les accès et la durée de conservation doivent être contrôlés." />
  @if(error()){<p role="alert" class="alert-error">{{error()}}</p>}
  @if(success()){<p role="status" class="alert-ok">{{success()}}</p>}
  <section class="card p-6">
    <h2 class="text-lg font-bold">Durée de conservation</h2>
    <p class="mt-1 text-sm text-slate-500">Définir une durée indicative de 30 à 3 650 jours. L'administrateur reste responsable de vérifier les obligations légales et les campagnes clôturées.</p>
    <form class="mt-4 flex max-w-md flex-wrap items-end gap-3" (ngSubmit)="savePolicy()">
      <label class="flex-1"><span class="field-label">Nombre de jours</span><input class="field" name="days" type="number" min="30" max="3650" [(ngModel)]="days" required/></label>
      <button class="btn-primary" [disabled]="busy() || days < 30 || days > 3650" type="submit"><tr-icon name="check" [size]="16" class="inline-flex align-middle mr-1"/>Enregistrer</button>
    </form>
  </section>
  <section class="card p-6">
    <h2 class="text-lg font-bold">Candidatures potentiellement arrivées à échéance</h2>
    <p class="my-2 text-sm text-slate-500">Liste indicative des dossiers anciens, sans conservation légale, associés uniquement à des campagnes clôturées. Aucune suppression n'est effectuée ici.</p>
    <button class="btn-light" [disabled]="busy()" (click)="loadDue()">Actualiser la liste</button>
    @if(due().length){<div class="mt-4 overflow-x-auto"><table class="w-full"><thead><tr><th class="text-left">Référence</th><th>Création</th><th>Documents</th><th></th></tr></thead><tbody>
    @for(c of due(); track c.id){<tr class="border-t border-slate-100 dark:border-slate-800"><td class="py-3">{{c.reference}}</td><td>{{c.created_at.slice(0,10)}}</td><td>{{c.documents}}</td><td><button class="btn-light" (click)="select(c.id)">Examiner</button></td></tr>}
    </tbody></table></div>}
    @else{<p class="mt-4 text-sm text-slate-500">Aucun dossier signalé dans l'échantillon consulté.</p>}
  </section>
  <section class="card p-6">
    <h2 class="text-lg font-bold">Demande de suppression d'un candidat</h2>
    <p class="mt-1 text-sm text-slate-500">La suppression touche ses CV, ses preuves, ses candidatures et les analyses communes. Elle ne supprime pas les copies exportées ni les sauvegardes externes.</p>
    <form class="mt-4 flex flex-wrap items-end gap-3" (ngSubmit)="previewCandidate()">
      <label class="min-w-56 flex-1"><span class="field-label">Identifiant du candidat</span><input class="field" name="candidate" [(ngModel)]="candidateId" (ngModelChange)="invalidatePreview()" required placeholder="UUID du candidat"/></label>
      <button class="btn-light" [disabled]="busy() || !candidateId.trim()" type="submit">Vérifier les impacts</button>
    </form>
    @if(preview() && previewFor()===candidateId.trim()){
      <div class="mt-4 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
        <p><b>{{preview()!.documents}}</b> documents, <b>{{preview()!.applications}}</b> candidatures, <b>{{preview()!.analyses_impactees}}</b> analyses impactées.</p>
        <p class="mt-2 text-sm text-slate-500">{{preview()!.warning}}</p>
        <label class="mt-4 block"><span class="field-label">Motif de conservation légale (minimum 12 caractères)</span><textarea class="field" rows="2" name="holdReason" [(ngModel)]="holdReason" placeholder="Base et référence de l'obligation"></textarea></label>
        <button class="btn-light mt-2" type="button" [disabled]="busy() || holdReason.trim().length < 12" (click)="setHold(!preview()!.legal_hold)">{{preview()!.legal_hold ? 'Lever la conservation' : 'Activer la conservation légale'}}</button>
        @if(preview()!.legal_hold){<p class="mt-3 text-red-700" role="alert">Suppression bloquée par une conservation légale.</p>}
        @else{
          <label class="mt-4 block"><span class="field-label">Saisir SUPPRIMER pour confirmer cette opération irréversible</span><input class="field" name="confirmation" [(ngModel)]="confirmation" autocomplete="off"/></label>
          <button class="mt-3 rounded-lg bg-red-700 px-4 py-2 text-white disabled:opacity-50" type="button" [disabled]="busy() || confirmation !== 'SUPPRIMER'" (click)="erase()">Supprimer le dossier et ses données dérivées</button>
        }
      </div>
    }
  </section>
</section>`})
export class PrivacyPage implements OnInit {
  private http = inject(HttpClient);
  readonly busy=signal(false); readonly error=signal(''); readonly success=signal('');
  readonly due=signal<Due[]>([]); readonly preview=signal<Preview|null>(null); readonly previewFor=signal('');
  days=365;candidateId='';confirmation='';holdReason='';
  ngOnInit(){void this.load();}
  async load(){this.error.set('');try{const p=await firstValueFrom(this.http.get<Policy>('/api/v1/privacy/retention'));this.days=p.retention_days;await this.loadDue();}catch(e){this.error.set(apiError(e));}}
  async loadDue(){try{const result=await firstValueFrom(this.http.get<{items:Due[]}>('/api/v1/privacy/candidates/due'));this.due.set(result.items);}catch(e){this.error.set(apiError(e));}}
  async savePolicy(){this.busy.set(true);this.error.set('');try{await firstValueFrom(this.http.put('/api/v1/privacy/retention',{retention_days:this.days}));this.success.set('Politique enregistrée. Aucun effacement automatique.');await this.loadDue();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
  select(id:string){this.candidateId=id;this.invalidatePreview();void this.previewCandidate();}
  invalidatePreview(){this.preview.set(null);this.previewFor.set('');this.confirmation='';}
  async setHold(active:boolean){this.busy.set(true);this.error.set('');try{await firstValueFrom(this.http.put(`/api/v1/privacy/candidates/${encodeURIComponent(this.candidateId)}/hold`,{active,reason:this.holdReason}));this.success.set(active?'Conservation légale activée.':'Conservation légale levée.');this.preview.set(null);this.confirmation='';await this.loadDue();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}await this.previewCandidate();}
  async previewCandidate(){const id=this.candidateId.trim();if(!id)return;this.busy.set(true);this.error.set('');this.invalidatePreview();try{const p=await firstValueFrom(this.http.get<Preview>(`/api/v1/privacy/candidates/${encodeURIComponent(id)}/erasure-preview`));if(id===this.candidateId.trim()){this.preview.set(p);this.previewFor.set(id);}}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
  async erase(){if(this.confirmation!=='SUPPRIMER'||!this.preview()||this.previewFor()!==this.candidateId.trim()||this.preview()!.legal_hold)return;this.busy.set(true);this.error.set('');try{const target=this.candidateId;await firstValueFrom(this.http.post(`/api/v1/privacy/candidates/${encodeURIComponent(target)}/erase`,{confirmation:this.confirmation}));this.preview.set(null);this.confirmation='';this.candidateId='';this.success.set('Données actives supprimées. Vérifier séparément les sauvegardes et les copies exportées.');await this.loadDue();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
