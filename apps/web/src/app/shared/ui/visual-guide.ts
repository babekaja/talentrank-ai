import {ChangeDetectionStrategy, Component, Input} from '@angular/core';

/** Compact, optional orientation panel. It never reports model output. */
@Component({selector:'tr-visual-guide',standalone:true,
 changeDetection:ChangeDetectionStrategy.OnPush,
 template:`<aside class="tr-visual-guide" aria-label="Conseil pour cette étape">
  <div class="tr-visual-guide__text"><p class="tr-visual-guide__title">{{title}}</p><p class="tr-visual-guide__description">{{description}}</p></div>
 </aside>`})
export class VisualGuide {
 @Input({required:true}) title = '';
 @Input({required:true}) description = '';
}
