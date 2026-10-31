import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';
import { unsavedGuard } from './core/guards/unsaved.guard';

const recruitmentRoles = ['org_admin','recruiter'] as const;
const adminRoles = ['org_admin'] as const;
const evaluatorRoles = ['evaluator'] as const;
export const routes: Routes = [
 {path:'connexion',title:'Connexion | TalentRank AI',canActivate:[guestGuard],loadComponent:()=>import('./features/login/login').then(m=>m.Login)},
 {path:'inscription',title:'Créer un compte | TalentRank AI',canActivate:[guestGuard],loadComponent:()=>import('./features/register/register').then(m=>m.Register)},
 {path:'espace-candidat',loadComponent:()=>import('./features/portal/candidate-portal').then(m=>m.CandidatePortal)},
 {path:'invitation',loadComponent:()=>import('./features/invitation/invitation').then(m=>m.InvitationPage)},
 {path:'',canActivate:[authGuard],loadComponent:()=>import('./features/shell/shell').then(m=>m.Shell),children:[
  {path:'',loadComponent:()=>import('./features/system/home-redirect').then(m=>m.HomeRedirect)},
  {path:'tableau-de-bord',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/dashboard/dashboard').then(m=>m.Dashboard)},
  {path:'demarrer',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/onboarding/getting-started').then(m=>m.GettingStarted)},
  {path:'offres',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/jobs/jobs').then(m=>m.Jobs)},
  {path:'offres/nouvelle',canDeactivate:[unsavedGuard],canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/jobs/job-editor').then(m=>m.JobEditor)},
  {path:'offres/:id',canDeactivate:[unsavedGuard],canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/jobs/job-editor').then(m=>m.JobEditor)},
  {path:'campagnes',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/campaigns/campaigns').then(m=>m.Campaigns)},
  {path:'campagnes/:id',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/campaigns/campaign-detail').then(m=>m.CampaignDetail)},
  {path:'candidats',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/candidates/candidates').then(m=>m.Candidates)},
  {path:'candidats/:id',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/candidates/candidate-detail').then(m=>m.CandidateDetail)},
  {path:'candidatures',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/applications/applications').then(m=>m.Applications)},
  {path:'affectations',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/reviews/assignments').then(m=>m.AssignmentsPage)},
  {path:'mes-examens',canActivate:[roleGuard],data:{roles:evaluatorRoles},loadComponent:()=>import('./features/reviews/my-reviews').then(m=>m.MyReviews)},
  {path:'formations',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/training/training').then(m=>m.TrainingPage)},
  {path:'importations',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/uploads/uploads').then(m=>m.Uploads)},
  {path:'documents/:id/competences',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/skills/document-skills').then(m=>m.DocumentSkills)},
  {path:'competences/:id/synonymes',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/skills/aliases').then(m=>m.SkillAliases)},
  {path:'competences',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/skills/skills').then(m=>m.Skills)},
  {path:'talentgraph-africa',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/africa/talentgraph').then(m=>m.TalentGraph)},
  {path:'prooflab-africa',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/africa/prooflab').then(m=>m.ProofLab)},
  {path:'documents/:id/preuves',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/africa/skillsproof').then(m=>m.SkillsProof)},
  {path:'matching/resultat/:id/opportunites',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/africa/opportunity-bridge').then(m=>m.OpportunityBridge)},
  {path:'laboratoire-ml',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/ml/ml-lab').then(m=>m.MlLab)},
  {path:'recherche-semantique',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/semantic/semantic').then(m=>m.SemanticSearch)},
  {path:'documents/:id',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/documents/document-detail').then(m=>m.DocumentDetail)},
  {path:'rapports',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/insights/reports').then(m=>m.Reports)},
  {path:'documents/:id/visionneuse',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/insights/document-viewer').then(m=>m.DocumentViewer)},
  {path:'documents/:id/controle',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/insights/document-quality').then(m=>m.DocumentQuality)},
  {path:'matching/resultat/:id/ecarts',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/insights/skill-gaps').then(m=>m.SkillGaps)},
  {path:'matching',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/matching/matching').then(m=>m.MatchingPage)},
  {path:'matching/analyses/:id/comparer',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/matching/matching-compare').then(m=>m.MatchingCompare)},
  {path:'matching/resultat/:id',canActivate:[roleGuard],data:{roles:recruitmentRoles},loadComponent:()=>import('./features/matching/matching-detail').then(m=>m.MatchingDetail)},
  {path:'equipe',canActivate:[roleGuard],data:{roles:adminRoles},loadComponent:()=>import('./features/team/team').then(m=>m.Team)},
  {path:'audit',canActivate:[roleGuard],data:{roles:adminRoles},loadComponent:()=>import('./features/audit/audit').then(m=>m.AuditPage)},
  {path:'confidentialite',canActivate:[roleGuard],data:{roles:adminRoles},loadComponent:()=>import('./features/privacy/privacy').then(m=>m.PrivacyPage)},
  {path:'parametres',loadComponent:()=>import('./features/settings/settings').then(m=>m.SettingsPage)},
  {path:'acces-refuse',loadComponent:()=>import('./features/system/access-denied').then(m=>m.AccessDenied)},
 ]},
 {path:'**',loadComponent:()=>import('./features/system/not-found').then(m=>m.NotFound)}
];
