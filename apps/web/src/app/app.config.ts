import { provideLucideIcons, LucideArrowDownUp, LucideArrowLeft, LucideArrowRight, LucideArrowUpRight, LucideBookOpen, LucideBrain, LucideBriefcaseBusiness, LucideCalendarDays, LucideChartColumn, LucideChartNoAxesCombined, LucideCircleCheck, LucideCircleHelp, LucideClipboardCheck, LucideClock3, LucideDownload, LucideEye, LucideFileText, LucideFilter, LucideFolderOpen, LucideGitCompareArrows, LucideGraduationCap, LucideHistory, LucideInfo, LucideLayers3, LucideLayoutDashboard, LucideListChecks, LucideLockKeyhole, LucideLogOut, LucideMail, LucideMenu, LucideMessageSquareText, LucidePencil, LucidePlus, LucideRefreshCw, LucideSearch, LucideSettings2, LucideShieldCheck, LucideSlidersHorizontal, LucideSparkles, LucideTarget, LucideTrash2, LucideTriangleAlert, LucideUpload, LucideUserRound, LucideUsers, LucideUsersRound, LucideX } from '@lucide/angular';
import { ApplicationConfig, inject, provideAppInitializer, provideZonelessChangeDetection } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { AuthService } from './core/auth/auth.service';
import { authInterceptor } from './core/auth/auth.interceptor';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection(),
    provideLucideIcons(LucideArrowDownUp, LucideArrowLeft, LucideArrowRight, LucideArrowUpRight, LucideBookOpen, LucideBrain, LucideBriefcaseBusiness, LucideCalendarDays, LucideChartColumn, LucideChartNoAxesCombined, LucideCircleCheck, LucideCircleHelp, LucideClipboardCheck, LucideClock3, LucideDownload, LucideEye, LucideFileText, LucideFilter, LucideFolderOpen, LucideGitCompareArrows, LucideGraduationCap, LucideHistory, LucideInfo, LucideLayers3, LucideLayoutDashboard, LucideListChecks, LucideLockKeyhole, LucideLogOut, LucideMail, LucideMenu, LucideMessageSquareText, LucidePencil, LucidePlus, LucideRefreshCw, LucideSearch, LucideSettings2, LucideShieldCheck, LucideSlidersHorizontal, LucideSparkles, LucideTarget, LucideTrash2, LucideTriangleAlert, LucideUpload, LucideUserRound, LucideUsers, LucideUsersRound, LucideX),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAppInitializer(() => inject(AuthService).initialize()),
  ]
};
