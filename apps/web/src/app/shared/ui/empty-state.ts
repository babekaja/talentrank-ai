import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideInbox } from '@lucide/angular';
import { TrIllustration, IllustrationName } from './tr-illustration';

/** A next-step-oriented empty state; never creates placeholder business data. */
@Component({
  selector: 'tr-empty-state', standalone: true, imports: [RouterLink, LucideInbox, TrIllustration],
  template: `
  <div class="px-6 py-12 text-center" role="status">
    @if(illustration){<tr-illustration class="tr-empty-visual" [name]="illustration" />}@else{<div class="empty-illustration" aria-hidden="true"><svg lucideInbox [size]="26" /></div>}
    <h3 class="text-lg font-bold text-slate-900 dark:text-white">{{title}}</h3>
    <p class="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-600 dark:text-slate-300">{{description}}</p>
    @if(actionLabel && actionRoute){<a class="btn-primary mt-5" [routerLink]="actionRoute">{{actionLabel}}</a>}
  </div>`
})
export class EmptyState {
  @Input({required:true}) title = '';
  @Input({required:true}) description = '';
  @Input() actionLabel = '';
  @Input() actionRoute = '';
  @Input() illustration: IllustrationName | null = null;
}
