import { TrIllustration } from '../../shared/ui/tr-illustration';
import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';
import { TrIcon } from '../../shared/ui/tr-icon';
import { apiError } from '../../shared/recruitment';

interface Mention {start:number;end:number;text:string;label:string;status:string}
interface Page {number:number;text:string;method:string;mentions:Mention[]}
interface Viewer {document_id:string;filename:string;total_pages:number;pages:Page[];note:string}
interface Part {value:string;marked:boolean;label:string;focus:boolean}

@Component({selector:'tr-document-viewer',standalone:true,imports:[TrIllustration, TrIcon,RouterLink],template:`
<header class="page-intro"><div><a routerLink="/importations" class="inline-link text-sm"><tr-icon name="arrow-left" [size]="16"/> Importations</a>
  <p class="eyebrow mt-4"><tr-icon name="search" [size]="16"/> Vérifier les informations</p>
  <h1>CV et preuves côte à côte</h1><p>Comparez le document d'origine aux passages reconnus. Les surlignages concernent la transcription, pas les coordonnées du PDF.</p></div>
  <a [routerLink]="['/documents',id,'controle']" class="btn-light"><tr-icon name="shield-check" [size]="17"/> Qualité de l'extraction</a>
</header>
@if(error()){<div class="alert-error mb-5" role="alert">{{error()}} <button type="button" class="underline ml-2" (click)="loadPage()">Réessayer</button></div>}
@if(loading()){<div class="card p-8" role="status"><tr-icon name="refresh" [size]="18"/> Chargement de la page du CV…</div>}
@if(viewer();as v){
  <section class="card mb-5 p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4" aria-label="Navigation dans le document">
    <div class="min-w-0"><p class="font-semibold break-all">{{v.filename}}</p><p class="text-xs muted mt-1">Page {{currentPage()}} sur {{v.total_pages}} · accès privé</p></div>
    <div class="flex items-center flex-wrap gap-2">
      <button type="button" class="btn-light" [disabled]="loading()||currentPage()<=1" (click)="changePage(currentPage()-1)" aria-label="Page précédente"><tr-icon name="arrow-left" [size]="17"/> Précédente</button>
      <label for="cv-page" class="text-sm font-medium">Page</label>
      <select class="field !w-20" id="cv-page" [value]="currentPage()" (change)="changePage(+$any($event.target).value)" [disabled]="loading()">
       @for(n of pageNumbers();track n){<option [value]="n">{{n}}</option>}
      </select>
      <button type="button" class="btn-light" [disabled]="loading()||currentPage()>=v.total_pages" (click)="changePage(currentPage()+1)">Suivante <tr-icon name="arrow-right" [size]="17"/></button>
    </div>
  </section>
  @if(v.total_pages===0){<div class="card p-5 mb-5 text-sm" role="status">Aucune page lisible enregistrée pour ce document. Relancez l’extraction ou demandez une vérification.</div>}
  @if(focused()){<div class="human-callout mb-5 p-4 text-sm" role="status"><tr-icon name="target" [size]="17"/> Passage demandé : page {{currentPage()}}. Le repère bleu signale la mention exacte lorsqu'elle est encore présente.</div>}
  <div class="grid gap-5 xl:grid-cols-2 xl:items-start">
    <section class="card min-w-0 overflow-hidden xl:sticky xl:top-5" aria-label="Document original">
      <div class="p-4 sm:p-5 border-b border-slate-200 dark:border-slate-700 flex flex-wrap justify-between gap-3 items-center">
        <div><h2 class="section-heading"><tr-icon name="file-text" [size]="19"/> Document original</h2><p class="section-caption mt-1">La vue PDF ne surligne pas les positions originales.</p></div>
        @if(isPdf()){
          <button class="btn-light" type="button" (click)="previewPdf()" [disabled]="previewBusy()"><tr-icon name="eye" [size]="17"/> {{previewBusy()?'Ouverture…':pdfUrl()?'Rafraîchir':'Afficher le PDF'}}</button>
        }
      </div>
      @if(pdfUrl()){<iframe [src]="pdfUrl()" class="w-full min-h-[470px] h-[68vh] bg-white" title="Aperçu privé du CV PDF"></iframe>}
      @else{<div class="min-h-[390px] p-8 flex flex-col justify-center items-center text-center gap-3">
        <tr-illustration name="secure-documents" class="tr-document-placeholder" /><h3 class="font-semibold">{{isPdf()?'Votre document reste privé':'Aperçu disponible sous forme de texte'}}</h3>
        <p class="section-caption max-w-md">{{isPdf()?'Cliquez sur « Afficher le PDF » pour le consulter en toute confidentialité.':'Ce fichier n’est pas un PDF. Utilisez la transcription et les preuves présentées à droite.'}}</p>
      </div>}
    </section>
    <section class="min-w-0 space-y-4" aria-label="Preuves reconnues dans le texte">
      <div class="card p-5"><div class="flex justify-between gap-4 flex-wrap"><div><h2 class="section-heading"><tr-icon name="search" [size]="19"/> Passages trouvés</h2><p class="section-caption mt-1">{{mentions().length}} mention(s) sur cette page, sans déduction de niveau d'expertise</p></div><span class="soft-badge">{{page()?.method || 'Texte extrait'}}</span></div>
        @if(mentions().length){<div class="mt-4 space-y-2">@for(m of mentions();track $index){
          <button type="button" class="w-full text-left rounded-xl border p-3 hover:border-indigo-400 dark:border-slate-700 focus-visible:outline" [class.border-blue-500]="isFocused(m)" (click)="focusMention(m)">
             <span class="text-sm font-semibold break-words">{{m.label}}</span><span class="block text-xs muted mt-1">« {{m.text}} » · {{m.status==='verified'?'Vérifié':'À consulter'}}</span>
          </button>}
        </div>}@else{<p class="section-caption mt-4">Aucune mention de compétence reconnue sur cette page. Cela ne signifie pas qu'aucune compétence n'y figure.</p>}
      </div>
      <article class="card p-5 sm:p-6"><div class="flex items-center justify-between mb-4 gap-3"><h2 class="section-heading">Transcription : page {{currentPage()}}</h2><span class="text-xs muted">Texte original conservé</span></div>
       @if(page();as p){@if(p.text){<div class="whitespace-pre-wrap break-words text-sm leading-8 text-slate-700 dark:text-slate-200" id="cv-transcription">@for(part of segments(p);track $index){@if(part.marked){<mark [attr.title]="part.label" [class]="part.focus ? 'rounded bg-blue-200 ring-2 ring-blue-500 text-slate-900 px-0.5' : 'rounded bg-amber-200 text-slate-900 px-0.5'">{{part.value}}</mark>}@else{<span>{{part.value}}</span>}}</div>}@else{<p class="section-caption">Le texte de cette page n'a pas été extrait. Une revue humaine ou un nouvel OCR peut être nécessaire.</p>}}
      </article>
    </section>
  </div>
  <p class="mt-5 text-xs muted">{{v.note}} Toute conclusion sur les qualifications nécessite l'examen du contexte documentaire.</p>
}
`})
export class DocumentViewer implements OnInit,OnDestroy {
  private readonly http=inject(HttpClient);
  private readonly route=inject(ActivatedRoute);
  private readonly sanitizer=inject(DomSanitizer);
  readonly viewer=signal<Viewer|null>(null);
  readonly currentPage=signal(1);
  readonly loading=signal(true);
  readonly previewBusy=signal(false);
  readonly error=signal('');
  readonly pdfUrl=signal<SafeResourceUrl|null>(null);
  readonly focusRange=signal<{start:number;end:number}|null>(null);
  readonly page=computed(()=>this.viewer()?.pages[0]??null);
  readonly mentions=computed(()=>(this.page()?.mentions??[]).filter(m=>this.validMention(m)));
  readonly focused=computed(()=>this.focusRange()!==null);
  readonly pageNumbers=computed(()=>Array.from({length:Math.min(Math.max(this.viewer()?.total_pages??1,1),150)},(_,i)=>i+1));
  private objectUrl:string|null=null;
  get id():string{return this.route.snapshot.paramMap.get('id')??'';}
  isPdf(){return this.viewer()?.filename.toLowerCase().endsWith('.pdf')??false;}
  ngOnInit(){
    const params=this.route.snapshot.queryParamMap;
    const page=Number(params.get('page'));
    if(Number.isSafeInteger(page)&&page>0&&page<=150)this.currentPage.set(page);
    const start=Number(params.get('start')),end=Number(params.get('end'));
    if(params.has('start')&&params.has('end')&&Number.isSafeInteger(start)&&Number.isSafeInteger(end)&&start>=0&&end>start){this.focusRange.set({start,end});}
    void this.loadPage();
  }
  ngOnDestroy(){this.releasePdf();}
  private releasePdf(){if(this.objectUrl)URL.revokeObjectURL(this.objectUrl);this.objectUrl=null;this.pdfUrl.set(null);}
  private validMention(m:Mention):boolean{const p=this.page();return !!p&&Number.isSafeInteger(m.start)&&Number.isSafeInteger(m.end)&&m.start>=0&&m.end>m.start&&m.end<=p.text.length&&p.text.slice(m.start,m.end)===m.text;}
  isFocused(m:Mention):boolean{const r=this.focusRange();return !!r&&m.start===r.start&&m.end===r.end;}
  focusMention(m:Mention){this.focusRange.set({start:m.start,end:m.end});}
  async changePage(n:number){if(!Number.isSafeInteger(n)||n<1||n>(this.viewer()?.total_pages??150)||n>150||n===this.currentPage())return;
    this.currentPage.set(n);this.focusRange.set(null);await this.loadPage();this.updatePdfAnchor();}
  async loadPage(){this.loading.set(true);this.error.set('');try{
    const v=await firstValueFrom(this.http.get<Viewer>(`/api/v1/documents/${encodeURIComponent(this.id)}/viewer`,{params:{page_number:this.currentPage()}}));
    this.viewer.set(v);
    const mark=this.focusRange();
    if(mark && !v.pages[0]?.mentions.some(m=>m.start===mark.start&&m.end===mark.end&&v.pages[0]?.text.slice(m.start,m.end)===m.text))this.focusRange.set(null);
  }catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
  segments(p:Page):Part[]{let cursor=0;const parts:Part[]=[];
    for(const m of [...this.mentions()].sort((a,b)=>a.start-b.start)){
      if(m.start<cursor)continue;
      if(m.start>cursor)parts.push({value:p.text.slice(cursor,m.start),marked:false,label:'',focus:false});
      parts.push({value:p.text.slice(m.start,m.end),marked:true,label:m.label+' · '+m.status,focus:this.isFocused(m)});
      cursor=m.end;
    }
    if(cursor<p.text.length)parts.push({value:p.text.slice(cursor),marked:false,label:'',focus:false});
    return parts;
  }
  private updatePdfAnchor(){if(this.objectUrl)this.pdfUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(`${this.objectUrl}#page=${this.currentPage()}`));}
  async previewPdf(){this.previewBusy.set(true);this.error.set('');try{
    if(!this.isPdf())throw new Error('L’aperçu PDF n’est pas disponible pour ce fichier.');
    const blob=await firstValueFrom(this.http.get(`/api/v1/documents/${encodeURIComponent(this.id)}/download`,{responseType:'blob'}));
    if(blob.type!=='application/pdf'&&blob.type!=='application/octet-stream')throw new Error('Le serveur n’a pas retourné de PDF valide.');
    this.releasePdf();this.objectUrl=URL.createObjectURL(new Blob([blob],{type:'application/pdf'}));this.updatePdfAnchor();
  }catch(e){this.error.set(apiError(e));}finally{this.previewBusy.set(false);}}
}
