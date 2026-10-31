import { Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Meta, Title } from '@angular/platform-browser';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

const pageMeta: Record<string, [string, string]> = {
  'connexion': ['Connexion', 'Accédez à votre espace de recrutement TalentRank AI.'],
  'espace-candidat': ['Espace candidat', 'Consultez vos préférences et gérez votre accord pour les suggestions de formation.'],
  'invitation': ['Invitation', 'Rejoignez votre organisation sur TalentRank AI avec un lien privé.'],
  'tableau-de-bord': ['Accueil', 'Suivez les candidatures et les prochaines actions de votre organisation.'],
  'demarrer': ['Bien démarrer', 'Les étapes pour préparer une offre et examiner les candidatures.'],
  'offres': ['Offres d’emploi', 'Créez et suivez les offres d’emploi de votre organisation.'],
  'campagnes': ['Campagnes', 'Organisez vos campagnes et les candidatures reçues.'],
  'candidats': ['Candidats', 'Consultez les fiches candidat accessibles à votre organisation.'],
  'candidatures': ['Candidatures', 'Examinez les dossiers et les avis humains de votre équipe.'],
  'affectations': ['Affectations', 'Répartissez les dossiers à examiner dans votre équipe.'],
  'mes-examens': ['Dossiers à examiner', 'Consultez les dossiers qui vous ont été affectés.'],
  'formations': ['Formations', 'Gérez les formations vérifiées proposées aux candidats.'],
  'importations': ['Dépôt de CV', 'Déposez et suivez le traitement des CV.'],
  'documents': ['Documents', 'Consultez les documents et les preuves extraites.'],
  'competences': ['Compétences', 'Consultez le référentiel de compétences.'],
  'talentgraph-africa': ['Graphe de compétences', 'Explorez les liens entre compétences.'],
  'prooflab-africa': ['Évaluation des méthodes', 'Consultez les contrôles expérimentaux des méthodes.'],
  'laboratoire-ml': ['Laboratoire ML', 'Consultez les évaluations des modèles expérimentaux.'],
  'recherche-semantique': ['Recherche avancée', 'Recherchez des mentions dans les documents autorisés.'],
  'rapports': ['Rapports', 'Préparez des rapports sur les candidatures de votre organisation.'],
  'matching': ['Analyse des CV', 'Examinez les correspondances et les preuves par critère.'],
  'equipe': ['Équipe', 'Gérez les membres et les permissions de votre organisation.'],
  'audit': ['Historique des actions', 'Consultez les actions enregistrées dans votre organisation.'],
  'confidentialite': ['Vie privée des candidats', 'Gérez la conservation des candidatures.'],
  'parametres': ['Préférences', 'Consultez votre compte et vos préférences.'],
  'acces-refuse': ['Accès limité', 'Cette page nécessite une autorisation supplémentaire.'],
};

@Component({ selector: 'tr-root', standalone: true, imports: [RouterOutlet], template: '<router-outlet />' })
export class App {
  private readonly router = inject(Router);
  private readonly title = inject(Title);
  private readonly meta = inject(Meta);

  constructor() {
    this.router.events.pipe(filter(event => event instanceof NavigationEnd), takeUntilDestroyed(inject(DestroyRef)))
      .subscribe(() => this.updatePageMeta());
    this.updatePageMeta();
  }

  private updatePageMeta(): void {
    const path = this.router.url.split('?')[0].split('/').filter(Boolean);
    const primary = path[0] ?? 'tableau-de-bord';
    let [title, description] = pageMeta[primary] ?? ['Page introuvable', 'Cette page est introuvable sur TalentRank AI.'];
    let leaf = this.router.routerState.snapshot.root;
    while (leaf.firstChild) leaf = leaf.firstChild;
    if (leaf.routeConfig?.path === '**') [title, description] = ['Page introuvable', 'Cette page est introuvable sur TalentRank AI.'];
    else if (primary === 'offres' && path[1] === 'nouvelle') title = 'Nouvelle offre';
    else if (primary === 'offres' && path.length > 1) title = 'Modifier une offre';
    else if (primary === 'campagnes' && path.length > 1) title = 'Détail de campagne';
    else if (primary === 'candidats' && path.length > 1) title = 'Fiche candidat';
    else if (primary === 'documents' && path.length > 2) title = 'Analyse du document';
    else if (primary === 'matching' && path.length > 2) title = 'Résultat de l’analyse';
    const fullTitle = `${title} | TalentRank AI`;
    this.title.setTitle(fullTitle);
    this.meta.updateTag({ name: 'description', content: description });
    this.meta.updateTag({ property: 'og:title', content: fullTitle });
    this.meta.updateTag({ property: 'og:description', content: description });
  }
}
