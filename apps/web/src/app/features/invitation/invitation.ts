import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { apiError } from '../../shared/recruitment';

@Component({selector:'tr-invitation',standalone:true,imports:[TrIcon,RouterLink,FormsModule],template:`
<main class="flex min-h-screen items-center justify-center bg-slate-100 p-5"><div class="card w-full max-w-lg p-8"><a routerLink="/connexion" class="text-sm font-bold text-indigo-700">TalentRank AI</a><h1 class="mt-5 text-2xl font-bold"><tr-icon name="mail" [size]="23" class="inline-flex align-middle mr-2"/> Rejoindre une organisation</h1><p class="mt-2 text-sm text-slate-500">Le lien d'invitation est valable 48 heures et utilisable une seule fois. Si vous avez déjà un compte, utilisez son mot de passe actuel.</p>
@if(error()){<p class="alert-error mt-5" role="alert">{{error()}}</p>}@if(done()){<p class="alert-ok mt-5">Invitation acceptée. Vous pouvez maintenant vous connecter avec l'adresse email invitée et le nom de l'organisation.</p><a routerLink="/connexion" class="btn-primary mt-4 inline-block">Connexion</a>}@else{
<form (ngSubmit)="accept()" class="mt-6 space-y-4"><label class="block"><span class="field-label">Nom complet (nouveau compte)</span><input class="field" name="name" [(ngModel)]="fullName" required minlength="2"/></label><label class="block"><span class="field-label">Mot de passe (12 caractères minimum)</span><input class="field" name="password" [(ngModel)]="password" type="password" minlength="12" required/></label><button class="btn-primary w-full" [disabled]="busy() || !token || password.length<12 || fullName.trim().length<2" type="submit">Accepter l'invitation</button></form>}
</div></main>`})
export class InvitationPage {
 private http=inject(HttpClient);private route=inject(ActivatedRoute);readonly error=signal('');readonly done=signal(false);readonly busy=signal(false);readonly token=this.route.snapshot.queryParamMap.get('token');fullName='';password='';
 async accept(){this.error.set('');this.busy.set(true);try{await firstValueFrom(this.http.post('/api/v1/invitations/accept',{token:this.token,full_name:this.fullName,password:this.password}));this.done.set(true);this.password='';}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
