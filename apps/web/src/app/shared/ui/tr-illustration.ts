import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

/** Decorative art only: never use these pictures as evidence, metrics or candidate photos. */
export type IllustrationName =
  | 'analytics-dashboard' | 'candidate-comparison' | 'candidate-decision'
  | 'candidate-onboarding' | 'candidate-ranking' | 'cv-import'
  | 'explainable-review' | 'fair-hiring' | 'interview-scheduling'
  | 'job-description' | 'matching-intelligent' | 'multilingual-analysis'
  | 'notifications' | 'recruitment-pipeline' | 'reports-export'
  | 'secure-documents' | 'skills-extraction' | 'system-health'
  | 'talent-search' | 'team-collaboration';

@Component({
  selector: 'tr-illustration', standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<img class="tr-illustration-img" [src]="url480" [attr.srcset]="srcset"
    sizes="(max-width: 640px) 180px, (max-width: 1024px) 210px, 260px"
    [attr.loading]="priority ? 'eager' : 'lazy'"
    [attr.fetchpriority]="priority ? 'high' : 'auto'"
    decoding="async" alt="" aria-hidden="true" />`
})
export class TrIllustration {
  @Input({required:true}) name: IllustrationName = 'cv-import';
  @Input() priority = false;
  get url480(): string { return `/assets/talentrank/${this.name}-480.webp`; }
  get srcset(): string { return `${this.url480} 480w, /assets/talentrank/${this.name}-960.webp 960w`; }
}
