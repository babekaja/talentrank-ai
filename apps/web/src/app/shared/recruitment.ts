import { HttpErrorResponse } from '@angular/common/http';

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface Requirement {
  id?: string; code: string; label: string;
  category: 'skill' | 'experience' | 'qualification' | 'certification' | 'language' | 'other';
  required: boolean; weight: number; justification: string; skill_ref: string | null; resolved_skill_id?: string|null;
}
export interface Job {
  id: string; title: string; description: string; department: string | null;
  location: string | null; contract_type: string | null; work_mode: 'onsite'|'remote'|'hybrid'|null;
  status: string; opens_on: string | null; closes_on: string | null;
  requirements: Requirement[]; criteria_version: number; criteria_confirmed_at: string | null;
  created_at: string;
}
export interface Campaign { id: string; job_id: string; name: string; status: string; created_at: string }
export interface Candidate { id: string; reference: string; full_name: string; email: string | null; phone: string | null; created_at: string }
export interface Application { id: string; candidate_id: string; campaign_id: string; review_status: string; created_at: string; candidate_reference?: string; candidate_name?: string; campaign_name?: string }
export interface Member { id: string; user_id: string; full_name: string; email: string; role: 'org_admin'|'recruiter'|'evaluator'; is_active: boolean }
export interface Invite { id: string; email: string; role: Member['role']; expires_at: string; accepted_at: string|null; revoked_at: string|null; token?: string }
export interface Audit { id: string; action: string; actor_id: string; resource_type: string; resource_id: string; details: Record<string, unknown>; created_at: string }

/** Convert technical HTTP failures into actionable French messages. */
export function apiError(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    if (err.status === 0) return 'Le service est momentanément inaccessible. Vérifiez votre connexion puis réessayez.';
    if (err.status === 401) return 'Votre session n’est plus active. Reconnectez-vous pour continuer.';
    if (err.status === 403) return err.error?.detail?.code==='DEMO_RESTRICTED'
      ? 'Mode démo : cette action nécessite une connexion avec vos propres identifiants.'
      : 'Vous n’avez pas accès à cette action. Demandez de l’aide à votre administrateur.';
    if (err.status === 404) return 'Cette information n’est plus disponible. Actualisez la page.';
    if (err.status === 413) {
      const detail = err.error?.detail;
      if (typeof detail === 'string' && detail.length <= 220 && !/(traceback|exception|sql|stack trace|internal server)/i.test(detail)) return detail;
      return 'Le fichier est trop volumineux. Réduisez sa taille ou demandez à votre administrateur de vérifier les limites.';
    }
    if (err.status === 429) return 'Vous avez effectué trop de demandes. Réessayez un peu plus tard.';
    if (err.status >= 500) return 'Une difficulté technique empêche cette action. Réessayez ou contactez votre équipe de support.';
    const detail = err.error?.detail;
    if (Array.isArray(detail)) return 'Certains champs sont incomplets ou incorrects. Vérifiez les informations saisies.';
    if (typeof detail === 'string' && detail.length <= 220 && !/(traceback|exception|sql|stack trace|internal server)/i.test(detail)) return detail;
    if (err.status === 422) return 'Vérifiez les champs du formulaire et réessayez.';
  }
  return 'Cette action n’a pas abouti. Vérifiez les informations et réessayez.';
}
