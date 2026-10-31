import { Component, Input } from '@angular/core';
@Component({
  selector:'tr-loading-state', standalone:true,
  template:`<div class="card p-6" role="status" aria-live="polite" [attr.aria-label]="label">
    <span class="sr-only">{{label}}</span>
    <div class="skeleton-line h-5 w-1/3"></div><div class="skeleton-line mt-6 h-11 w-full"></div>
    <div class="skeleton-line mt-3 h-11 w-full"></div><div class="skeleton-line mt-3 h-11 w-4/5"></div>
  </div>`
})
export class LoadingState { @Input() label='Chargement des données'; }
