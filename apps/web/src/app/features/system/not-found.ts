import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'tr-not-found',
  standalone: true,
  imports: [RouterLink],
  template: `
    <main class="flex min-h-screen items-center justify-center bg-[#f4f7f8] px-5 py-12 text-[#142a3e]">
      <section class="w-full max-w-lg border-l-4 border-[#245b93] bg-white px-7 py-10 sm:px-10">
        <p class="text-sm font-semibold uppercase tracking-wide text-[#245b93]">Erreur 404</p>
        <h1 class="mt-3 text-3xl font-bold">Cette page est introuvable</h1>
        <p class="mt-4 leading-7 text-[#536a7c]">L'adresse a peut-être changé. Vous pouvez revenir à l'accueil de TalentRank AI.</p>
        <a routerLink="/" class="btn-primary mt-7">Retour à l'accueil</a>
      </section>
    </main>
  `,
})
export class NotFound {}
