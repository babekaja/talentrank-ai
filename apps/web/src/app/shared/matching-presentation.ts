/** Presentation-only helpers. These labels never modify the matching calculation. */
export interface CoverageScope { evaluable_subset_coverage: number|null; assessable_weight_percent: number }
export interface DocumentaryEvidence {
  document_id: string; page_number: number; matched_text: string;
  start_offset: number; end_offset: number; source_still_matches: boolean;
  source_excerpt: string|null; verification_status_at_run: string;
}
export interface MatchingCriterion {
  code: string; label: string; group?: string; state: string;
  contribution: number; weight?: number; note_code?: string;
  evidence?: DocumentaryEvidence|null;
}
export interface MatchingResultView {
  rank?:number|null; matching_percentage?:number|null; ranking_scope_percent?:number;
  id:string; run_id?:string; candidate_reference_id:string; score:number|null;
  state:string; documented?:number; to_review?:number; not_documented?:number;
  criteria?:MatchingCriterion[]; group_coverage?:Record<string,unknown>;
}
export type CriterionFilter = 'all'|'documented'|'review'|'not_found';
export function criterionKind(state:string):Exclude<CriterionFilter,'all'>{
  if(state==='documented_mention')return 'documented';
  if(state==='not_documented'||state==='not_found')return 'not_found';
  return 'review';
}
export function criterionStatus(state:string):string {
  return ({documented_mention:'Mention documentée',needs_review:'À confirmer',
    manual_review_required:'Examen humain requis',awaiting_documents:'Document à traiter',
    not_documented:'Non retrouvé dans le CV',not_found:'Non retrouvé dans le CV'} as Record<string,string>)[state] ?? 'À examiner';
}
export function criterionReason(code:string):string {
  return ({EXACT_SOURCE_MENTION:'Une mention a été retrouvée dans le document.',
    AMBIGUOUS_MENTION:'Le passage ne permet pas de confirmer la compétence.',
    NO_MATCHING_DOCUMENT_MENTION:'Aucune mention correspondante n’a été retrouvée dans le texte analysé.',
    MANUAL_REVIEW_REQUIRED:'Ce critère exige un examen humain.',
    DOCUMENT_UNAVAILABLE:'Le document n’était pas exploitable lors de l’analyse.'} as Record<string,string>)[code] ?? 'Consultez la preuve et demandez une vérification si nécessaire.';
}
export function coverageScope(value:Record<string,unknown>|undefined):CoverageScope|null {
  const raw=value?.['summary'];
  if(!raw||typeof raw!=='object')return null;
  const record=raw as Record<string,unknown>;
  const pct=record['assessable_weight_percent'];
  const sub=record['evaluable_subset_coverage'];
  if(typeof pct!=='number'||!Number.isFinite(pct))return null;
  return {assessable_weight_percent:pct,evaluable_subset_coverage:typeof sub==='number'&&Number.isFinite(sub)?sub:null};
}
