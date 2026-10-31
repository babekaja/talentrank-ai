import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../auth/auth.service';
import { Me } from '../../shared/models/auth';
/** The backend remains authoritative. This guard avoids misleading screens and accidental requests. */
export const roleGuard: CanActivateFn = route => {
  const auth=inject(AuthService), router=inject(Router);
  if (!auth.user()) return router.createUrlTree(['/connexion']);
  const allowed=route.data['roles'] as ReadonlyArray<Me['role']> | undefined;
  return !allowed || allowed.includes(auth.user()!.role) ? true : router.createUrlTree(['/acces-refuse']);
};
