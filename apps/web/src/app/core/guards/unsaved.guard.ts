import { CanDeactivateFn } from '@angular/router';

export interface HasUnsavedForm { canLeave(): boolean }
/** Avoid losing unconfirmed offers or changed criteria during navigation. */
export const unsavedGuard: CanDeactivateFn<HasUnsavedForm> = component => component.canLeave();
