import { Pipe, PipeTransform } from '@angular/core';

/** Presentation only. Never changes an underlying status or business rule. */
@Pipe({name:'humanStatus', standalone:true, pure:true})
export class HumanStatus implements PipeTransform {
  transform(value: string | null | undefined, category: 'document'|'campaign'|'run'|'assignment'|'mention'|'generic' = 'generic'): string {
    if (!value) return 'Non renseigné';
    const common: Record<string,string> = {
      pending:'En attente',processing:'En cours',completed:'Terminé',failed:'Traitement impossible',
      needs_review:'À vérifier',confirmed:'Mention confirmée',rejected:'Mention écartée',
      planned:'Prévue',active:'En cours',closed:'Clôturée',draft:'Brouillon',
      assigned:'À examiner',revoked:'Accès retiré',shortlisted:'À discuter en équipe',
      ready:'Prêt',queued:'En attente de traitement',running:'En cours de traitement'
    };
    const specialized: Record<string, Record<string,string>> = {
      document: {uploaded:'CV reçu',extraction:'Lecture du document',ocr:'Lecture du document scanné',nlp:'Recherche des compétences',normalized:'Mentions enregistrées',needs_review:'Vérification nécessaire'},
      campaign: {active:'Ouverte',planned:'À préparer',closed:'Clôturée'},
      run: {completed:'Analyse terminée',partial_review_required:'Vérification nécessaire',awaiting_documents:'Documents attendus',documentary_coverage:'Couverture documentaire disponible'},
      assignment: {assigned:'À examiner',completed:'Avis enregistré',revoked:'Accès retiré'},
      mention: {documented:'Mention identifiée',confirmed:'Mention confirmée',needs_review:'Mention à vérifier',rejected:'Mention écartée',not_documented:'Non retrouvée',context_ambiguous:'Contexte incertain'},
      generic: {}
    };
    return specialized[category]?.[value] ?? common[value] ?? value.replace(/_/g,' ').replace(/^./,v=>v.toLocaleUpperCase('fr'));
  }
}
