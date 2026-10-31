import { TrIcon } from '../../shared/ui/tr-icon';
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
@Component({standalone:true,selector:'tr-access-denied',imports:[TrIcon,RouterLink],template:`
<section class="mx-auto max-w-xl py-14 text-center"><div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-100 dark:bg-indigo-950"><tr-icon name="lock" [size]="30"/></div>
<h1 class="mt-6 text-3xl font-bold"><tr-icon name="lock" [size]="23" class="inline-flex align-middle mr-2"/> Accès limité</h1><p class="mt-3 text-slate-500">Ce module nécessite une permission supplémentaire. Votre compte n'a pas accès aux données de recrutement ici. Demandez l'autorisation à l'administrateur de votre organisation.</p>
<a routerLink="/parametres" class="btn-primary mt-7 inline-block">Mon espace</a></section>`})
export class AccessDenied {}
