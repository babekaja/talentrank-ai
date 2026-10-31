import { VisualGuide } from '../../shared/ui/visual-guide';
import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { Campaign, Page, apiError } from '../../shared/recruitment';

interface Batch { id: string; campaign_id: string; created_at: string }
interface Progress {total:number;processed:number;completed:number;needs_review:number;failed:number;processing:number;pending:number}
interface CV {id:string;filename:string;status:string;error_code:string|null;page_count:number;application_id:string}
interface ImportOutcome {items:{status:string;filename:string}[]; failures?:{filename:string;message:string;code:number}[]; accepted?:number; rejected?:number}
@Component({selector:'tr-uploads',standalone:true,imports:[VisualGuide, TrIcon,FormsModule,RouterLink],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="upload" [size]="15"/> Vos documents</p><h1 class="mt-2">Importer des CV</h1><p>Déposez les documents d'une campagne. Vous pourrez suivre chaque étape et vérifier les informations extraites.</p></div></header>
<tr-visual-guide title="Après le dépôt des CV" description="Déposez les fichiers, puis suivez leur traitement avant de lire les informations extraites." />
@if(error()){<div role="alert" class="alert-error mb-5">{{error()}}</div>}
@if(info()){<div role="status" class="alert-ok mb-5">{{info()}}</div>}
@if(failedFiles().length){<section role="alert" class="alert-error mb-5" aria-label="Documents non importés"><h2 class="font-semibold">Certains CV n'ont pas été importés</h2><p class="text-sm mt-1">Les CV acceptés sont conservés. Vous pouvez corriger les fichiers suivants et les renvoyer.</p><ul class="mt-2 list-disc pl-5">@for(f of failedFiles();track $index){<li class="text-sm"><strong>{{f.filename}}</strong> : {{f.message}}</li>}</ul></section>}
<section class="card p-6 mb-6">
  <div class="mb-5"><h2 class="section-heading">1. Choisir les CV à ajouter</h2><p class="section-caption mt-1">Choisissez le recrutement concerné, puis les fichiers PDF ou Word. Vous pourrez vérifier leur lecture avant de les examiner.</p></div>
  <div class="grid gap-4 md:grid-cols-2">
    <label><span class="field-label">Campagne active</span><select class="field" [(ngModel)]="campaignId"><option value="">Sélectionner une campagne</option>@for(c of campaigns();track c.id){<option [value]="c.id">{{c.name}}</option>}</select></label>
    <label><span class="field-label">Ajouter les documents</span><input class="field" type="file" multiple accept=".pdf,.docx,.zip" (change)="fileChange($event)" aria-label="Choisir les CV"/></label>
  </div>
  <div class="mt-4 rounded-xl border-2 border-dashed border-[#a5c7d2] bg-[#f5fafb] px-5 py-8 text-center text-sm text-[#2c687a] dark:bg-slate-800" (dragover)="onDragOver($event)" (drop)="onDrop($event)" role="group" aria-label="Zone de dépôt des documents"><div class="flex flex-col items-center gap-2 pointer-events-none"><svg xmlns="http://www.w3.org/2000/svg" class="h-9 w-9 text-[#a5c7d2]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg><span class="font-semibold">Déposez vos fichiers ici</span><span class="text-[#4f8fa0]">PDF, DOCX ou ZIP · Glissez-déposez ou utilisez le bouton ci-dessus</span></div></div>
  <p class="text-sm text-slate-500 mt-3">Maximum 60 Mo par CV et 100 Mo par archive ZIP ; 3 000 documents par lot. Une archive ZIP est vérifiée avant extraction.</p>
  @if(files.length){<div class="mt-4 rounded-2xl border border-[#e2e8ea] p-4 dark:border-slate-700"><div class="mb-3 flex flex-wrap justify-between gap-3"><h3 class="font-semibold text-sm">Fichiers prêts à envoyer ({{files.length}})</h3><button class="text-sm font-semibold text-[#285888] underline dark:text-blue-200" type="button" [disabled]="busy()" (click)="files=[]">Tout retirer</button></div><ul class="space-y-2" aria-label="Fichiers sélectionnés">@for(f of files.slice(0,10);track $index){<li class="flex min-w-0 items-center justify-between gap-3 text-sm rounded-lg bg-[#f5fafb] px-3 py-2 dark:bg-slate-800"><span class="flex min-w-0 items-center gap-2 truncate"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 flex-shrink-0 text-[#a5c7d2]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg><span class="truncate">{{f.name}}</span></span><button type="button" class="text-xs font-semibold text-rose-700 underline dark:text-rose-200 flex-shrink-0" [disabled]="busy()" (click)="removeSelected($index)" [attr.aria-label]="'Retirer '+f.name">Retirer</button></li>}</ul>@if(files.length>10){<p class="mt-2 text-xs text-slate-500">Et {{files.length-10}} autre(s) fichier(s)…</p>}</div>}
  <div class="flex flex-wrap items-center gap-3 mt-5"><button class="btn-primary" (click)="submit()" [disabled]="busy() || !campaignId || !files.length">{{busy() ? 'Importation en cours…' : 'Envoyer les CV'}}</button>@if(busy()){<span role="status" class="text-sm text-slate-500">{{uploaded()}}/{{files.length}} fichiers envoyés</span>}</div>
</section>
<div class="grid gap-6 xl:grid-cols-[300px_1fr]">
  <section class="card overflow-hidden"><h2 class="px-5 py-4 text-lg font-bold border-b border-slate-100 dark:border-slate-800">Envois récents</h2>
    @if(!batches().length){<div class="p-5"><p class="font-semibold text-sm">Aucune importation encore</p><p class="section-caption mt-2">Les lots créés apparaîtront ici.</p></div>}
    @for(b of batches();track b.id){<button class="w-full text-left px-5 py-4 border-b border-slate-100 dark:border-slate-800 hover:bg-[#f5fafb] dark:hover:bg-slate-800 transition-colors" [class.bg-[#eaf4f7]]="selectedId()===b.id" [class.border-l-4]="selectedId()===b.id" [class.border-l-[#205f77]]="selectedId()===b.id" (click)="selectBatch(b.id)"><div class="flex items-center gap-2 mb-1"><svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 flex-shrink-0 text-[#4f8fa0]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke-linecap="round" stroke-linejoin="round"/><line x1="16" y1="2" x2="16" y2="6" stroke-linecap="round"/><line x1="8" y1="2" x2="8" y2="6" stroke-linecap="round"/><line x1="3" y1="10" x2="21" y2="10" stroke-linecap="round"/></svg><span class="font-semibold text-sm text-[#2c687a]">Lot {{b.id.slice(0,8)}}</span></div><small class="text-slate-500 text-xs">{{b.created_at.slice(0,16).replace('T',' ')}}</small></button>}
  </section>
  <section class="card overflow-hidden">
    @if(!selectedId()){<div class="p-8 text-center"><h3 class="font-bold">Choisissez un envoi</h3><p class="section-caption mt-2">Cliquez sur un envoi à gauche pour voir les CV reçus et leur état.</p></div>}
    @else{
      <div class="p-6 border-b border-slate-100 dark:border-slate-800">
        <h2 class="section-heading">2. Voir les CV reçus</h2><p class="section-caption mt-1">Les fichiers restent privés. Si un CV est illisible, vous pouvez reprendre son traitement.</p>
        @if(progress();as p){<p class="mt-3 text-sm">{{p.processed}} documents extraits sur {{p.total}}</p>
        <div class="h-2 mt-2 rounded-full overflow-hidden bg-slate-200 dark:bg-slate-700" role="progressbar" [attr.aria-valuenow]="p.processed" [attr.aria-valuemax]="p.total" aria-valuemin="0"><div class="h-full bg-[#205f77] transition-all" [style.width.%]="p.total ? p.processed*100/p.total : 0"></div></div>
        <div class="mt-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4"><span>Terminés : <b>{{p.completed}}</b></span><span>À vérifier : <b>{{p.needs_review}}</b></span><span>En cours : <b>{{p.processing}}</b></span><span>Échecs : <b>{{p.failed}}</b></span></div>}
      </div>
      <div class="overflow-x-auto"><table class="w-full min-w-[550px]"><thead class="table-head"><tr><th class="px-5 py-4">CV</th><th>État</th><th>Pages</th><th>Consultation</th><th>Action</th></tr></thead><tbody>
        @for(d of documents();track d.id){<tr><td class="table-td">{{d.filename}}</td><td class="table-td">@if(d.status==='completed'){<span class="text-[#176653] font-semibold">{{statusLabel(d.status)}}</span>}@else if(d.status==='failed'){<span class="text-rose-700 font-semibold">{{statusLabel(d.status)}}</span>}@else{<span class="text-slate-600">{{statusLabel(d.status)}}</span>}@if(d.error_code){<details class="mt-1 text-xs text-rose-700"><summary class="cursor-pointer">Pourquoi ?</summary><code class="block break-all">{{d.error_code}}</code></details>}</td><td class="table-td">{{d.page_count}}</td><td class="table-td"><a class="text-indigo-700 font-semibold hover:underline" [routerLink]="['/documents',d.id]">Ouvrir le CV</a></td><td class="table-td">@if(d.status==='failed'){<button type="button" class="btn-light" [disabled]="retryBusy()===d.id" (click)="retry(d.id)">{{retryBusy()===d.id?'Relance…':'Relancer'}}</button>}@else{<span class="text-slate-400">Sans action</span>}</td></tr>}
      </tbody></table></div>
      @if(!documents().length){<p class="p-5 text-slate-500">Aucun CV pour le moment.</p>}
      <div class="flex justify-between items-center p-4 text-sm"><span>{{docTotal()}} document(s)</span><div class="flex gap-2"><button class="btn-light" [disabled]="offset()===0" (click)="page(-1)">Précédent</button><button class="btn-light" [disabled]="offset()+25>=docTotal()" (click)="page(1)"><tr-icon name="arrow-right" [size]="16" class="inline-flex align-middle mr-1"/>Suivant</button></div></div>
    }
  </section>
</div>`})
export class Uploads implements OnInit,OnDestroy {
  private http=inject(HttpClient); private timer?:ReturnType<typeof setInterval>;
  readonly campaigns=signal<Campaign[]>([]);readonly batches=signal<Batch[]>([]);
  readonly documents=signal<CV[]>([]);readonly progress=signal<Progress|null>(null);
  readonly selectedId=signal('');readonly error=signal('');readonly info=signal('');readonly busy=signal(false);
  readonly uploaded=signal(0);readonly docTotal=signal(0);readonly offset=signal(0);readonly retryBusy=signal('');
  readonly failedFiles=signal<{filename:string;message:string}[]>([]);
  campaignId='';files:File[]=[];
  ngOnInit(){void this.init();this.timer=setInterval(()=>{if(this.selectedId()&&!this.busy())void this.refresh();},3000);}
  ngOnDestroy(){if(this.timer)clearInterval(this.timer);}
  async init(){try{const [campaigns,batches]=await Promise.all([firstValueFrom(this.http.get<Page<Campaign>>('/api/v1/campaigns?limit=100')),firstValueFrom(this.http.get<Page<Batch>>('/api/v1/uploads/batches?limit=25'))]);this.campaigns.set(campaigns.items.filter(c=>c.status==='active'));this.batches.set(batches.items);if(batches.items.length)this.selectBatch(batches.items[0].id);}catch(e){this.error.set(apiError(e));}}
  onDragOver(event:DragEvent){event.preventDefault();}
  onDrop(event:DragEvent){event.preventDefault();if(!this.busy())this.files=Array.from(event.dataTransfer?.files??[]);}
  removeSelected(index:number){if(!this.busy())this.files=this.files.filter((_,i)=>i!==index);}
  fileChange(event:Event){const input=event.target as HTMLInputElement;this.files=Array.from(input.files??[]);}
  async submit(){if(!this.campaignId || !this.files.length)return;
    this.busy.set(true);this.error.set('');this.info.set('');this.failedFiles.set([]);this.uploaded.set(0);
    try{
      const batch=await firstValueFrom(this.http.post<Batch>('/api/v1/uploads/batches',{campaign_id:this.campaignId}));
      this.batches.update(v=>[batch,...v]);this.selectedId.set(batch.id);
      let accepted=0;let duplicates=0;
      const failed:{filename:string;message:string}[]=[];
      // At most 3 uploads concurrently. Each ZIP can contain many documents.
      for(let i=0;i<this.files.length;i+=3){const group=this.files.slice(i,i+3);
        await Promise.all(group.map(async file=>{
          try{
            const body=new FormData();body.append('file',file,file.name);
            const outcome=await firstValueFrom(this.http.post<ImportOutcome>(`/api/v1/uploads/batches/${batch.id}/files`,body));
            accepted+=outcome.accepted??outcome.items.filter(item=>item.status!=='duplicate').length;
            duplicates+=outcome.items.filter(item=>item.status==='duplicate').length;
            for(const issue of outcome.failures??[])failed.push({filename:issue.filename,message:issue.message});
          }catch(e){failed.push({filename:file.name,message:apiError(e)});}
          finally{this.uploaded.update(v=>v+1);}
        }));
      }
      this.failedFiles.set(failed);
      this.info.set(`${accepted} CV accepté(s), ${duplicates} doublon(s), ${failed.length} fichier(s) non importé(s). Consultez les documents ci-dessous.`);
      this.files=[];await this.refresh();
    }catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}
  }
  selectBatch(id:string){this.selectedId.set(id);this.offset.set(0);void this.refresh();}
  page(delta:number){this.offset.update(v=>Math.max(0,v+25*delta));void this.refresh();}
  async refresh(){const id=this.selectedId();if(!id)return;try{const [p,d]=await Promise.all([firstValueFrom(this.http.get<Progress>(`/api/v1/uploads/batches/${id}/progress`)),firstValueFrom(this.http.get<Page<CV>>(`/api/v1/uploads/batches/${id}/documents?limit=25&offset=${this.offset()}`))]);if(id===this.selectedId()){this.progress.set(p);this.documents.set(d.items);this.docTotal.set(d.total);}}catch(e){this.error.set(apiError(e));}}
  async retry(id:string){this.retryBusy.set(id);this.error.set('');this.info.set('');try{await firstValueFrom(this.http.post(`/api/v1/documents/${id}/retry`,{}));this.info.set('Document replacé dans la file de traitement.');await this.refresh();}catch(e){this.error.set(apiError(e));}finally{this.retryBusy.set('');}}
  statusLabel(s:string){return ({pending:'En attente',processing:'Extraction en cours',completed:'Texte extrait',needs_review:'À vérifier',failed:'Échec'} as Record<string,string>)[s]??s;}
}
