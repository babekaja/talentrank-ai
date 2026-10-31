import { Component, Input, Type } from '@angular/core';
import { NgComponentOutlet } from '@angular/common';
import {
  LucideArrowLeft, LucideArrowRight, LucideArrowUpRight, LucideBookOpen,
  LucideBrain, LucideBriefcaseBusiness, LucideCalendarDays,
  LucideChartColumn, LucideChartNoAxesColumn, LucideChartNoAxesCombined,
  LucideCircleCheck, LucideCircleHelp, LucideClipboard, LucideClipboardCheck,
  LucideClock3, LucideColumns3, LucideEye, LucideFileSearch, LucideFileText,
  LucideFolderOpen, LucideGitCompareArrows, LucideGraduationCap,
  LucideHistory, LucideInfo, LucideLayers3, LucideLayoutDashboard,
  LucideListChecks, LucideLockKeyhole, LucideLogOut, LucideMail,
  LucideMessageSquareText, LucideRefreshCw, LucideSearch, LucideSettings2,
  LucideShieldCheck, LucideSlidersHorizontal, LucideTarget, LucideTrash2,
  LucideTriangleAlert, LucideUpload, LucideUserRound, LucideUsers,
  LucideUsersRound, LucideX, LucideArrowDownUp, LucidePlus
} from '@lucide/angular';

/** Unified, tree-shaken Lucide icon; decorative by default. */
const ICON_ALIASES: Record<string,string> = {
  dashboard:'layout-dashboard', briefcase:'briefcase-business', user:'user-round', file:'file-text',
  reports:'chart-no-axes-combined', history:'history', settings:'settings-2',
  shield:'shield-check', check:'circle-check', alert:'triangle-alert', help:'circle-help',
  clock:'clock-3', calendar:'calendar-days', refresh:'refresh-cw',
  external:'arrow-up-right', sort:'arrow-down-up', sliders:'sliders-horizontal',
  compare:'git-compare-arrows', clipboard:'clipboard-check', graduation:'graduation-cap',
  list:'list-checks', folder:'folder-open', lock:'lock-keyhole',
  trash:'trash-2', layers:'layers-3', people:'users-round',
  message:'message-square-text', chart:'chart-column', book:'book-open'
};

const ICON_COMPONENTS: Record<string, Type<unknown>> = {
  'arrow-left': LucideArrowLeft, 'arrow-right': LucideArrowRight,
  'arrow-up-right': LucideArrowUpRight, 'arrow-down-up': LucideArrowDownUp,
  'book-open': LucideBookOpen, brain: LucideBrain,
  'briefcase-business': LucideBriefcaseBusiness, 'calendar-days': LucideCalendarDays,
  'chart-column': LucideChartColumn, 'chart-no-axes-column': LucideChartNoAxesColumn,
  'chart-no-axes-combined': LucideChartNoAxesCombined,
  'circle-check': LucideCircleCheck, 'circle-help': LucideCircleHelp,
  clipboard: LucideClipboard, 'clipboard-check': LucideClipboardCheck,
  'clock-3': LucideClock3, 'columns-3': LucideColumns3, eye: LucideEye,
  'file-search': LucideFileSearch, 'file-text': LucideFileText,
  'folder-open': LucideFolderOpen, 'git-compare-arrows': LucideGitCompareArrows,
  'graduation-cap': LucideGraduationCap, history: LucideHistory, info: LucideInfo,
  'layers-3': LucideLayers3, 'layout-dashboard': LucideLayoutDashboard,
  'list-checks': LucideListChecks, 'lock-keyhole': LucideLockKeyhole,
  'log-out': LucideLogOut, mail: LucideMail,
  'message-square-text': LucideMessageSquareText, 'refresh-cw': LucideRefreshCw,
  search: LucideSearch, 'settings-2': LucideSettings2,
  'shield-check': LucideShieldCheck, 'sliders-horizontal': LucideSlidersHorizontal,
  target: LucideTarget, 'trash-2': LucideTrash2, 'triangle-alert': LucideTriangleAlert,
  upload: LucideUpload, 'user-round': LucideUserRound, users: LucideUsers,
  'users-round': LucideUsersRound, x: LucideX, plus: LucidePlus
};

@Component({
  selector: 'tr-icon', standalone: true, imports: [NgComponentOutlet],
  template: `<span class="inline-flex align-middle" [attr.aria-hidden]="label ? null : 'true'"
                   [attr.role]="label ? 'img' : null" [attr.aria-label]="label || null">
    <ng-container *ngComponentOutlet="iconComponent; inputs: iconInputs" />
  </span>`
})
export class TrIcon {
  @Input({required:true}) name = 'info';
  @Input() size = 18;
  @Input() label = '';
  get resolvedName(): string {return ICON_ALIASES[this.name] ?? this.name;}
  get iconComponent(): Type<unknown> {
    return ICON_COMPONENTS[this.resolvedName] ?? LucideInfo;
  }
  get iconInputs(): Record<string, number> {return {size: this.size, strokeWidth: 1.8};}
}
