import {Component, OnInit, inject} from '@angular/core';
import {Router} from '@angular/router';
import {AuthService} from '../../core/auth/auth.service';
@Component({selector:'tr-home-redirect',standalone:true,template:`<p role="status">Ouverture de votre espace…</p>`})
export class HomeRedirect implements OnInit {
 private auth=inject(AuthService);private router=inject(Router);
 ngOnInit(){void this.router.navigateByUrl(this.auth.user()?.role==='evaluator'?'/mes-examens':'/tableau-de-bord',{replaceUrl:true});}
}
