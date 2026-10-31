import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { MatchingPage } from './matching';

describe('Classement pondéré des CV', () => {
  let fixture: ComponentFixture<MatchingPage>;
  let http: HttpTestingController;
  const run = (processed: number, status = 'running', campaign = 'campaign-a') => ({
    id: `run-${campaign}`, campaign_id: campaign, job_id: 'job-test', total: 200, processed,
    status, criteria_version: 1, config_version: 1, algorithm_version: 'test',
    created_at: '2026-10-30T10:00:00', completed_at: status === 'completed' ? '2026-10-30T10:01:00' : null,
  });
  const ranked = [
    {id:'result-a',application_id:'application-a',candidate_reference_id:'candidate-a',candidate_reference:'DOSSIER-A',candidate_name:'Profil fictif A',rank:1,matching_percentage:81.25,ranking_scope_percent:80,score:null,state:'partial_review_required',documented:2,to_review:1,not_documented:1,group_coverage:{}},
    {id:'result-b',application_id:'application-b',candidate_reference_id:'candidate-b',candidate_reference:'DOSSIER-B',candidate_name:'Profil fictif B',rank:2,matching_percentage:43.75,ranking_scope_percent:80,score:null,state:'partial_review_required',documented:2,to_review:1,not_documented:1,group_coverage:{}},
  ];
  const results = () => http.expectOne(req => req.url.endsWith('/results')).flush({ items: ranked, total: 2, ranking:{assessed_weight_percent:80,criteria_count:3,ranked_count:2,unranked_count:0,provisional:false} });

  beforeEach(async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    TestBed.configureTestingModule({ imports: [MatchingPage], providers: [
      provideHttpClient(), provideHttpClientTesting(), provideRouter([]),
    ] });
    fixture = TestBed.createComponent(MatchingPage);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne('/api/v1/campaigns?limit=100').flush({ items: [
      { id: 'campaign-a', job_id: 'job-test', name: 'Campagne A', status: 'active' },
      { id: 'campaign-b', job_id: 'job-test', name: 'Campagne B', status: 'active' },
    ] });
    http.expectOne('/api/v1/matching/configuration').flush({ version: 1, weights: {
      essential: 60, desirable: 20, experience: 10, projects_training: 10,
    } });
    await vi.advanceTimersByTimeAsync(0);
    http.expectOne(req => req.url === '/api/v1/matching-runs').flush({ items: [run(50)] });
    await vi.advanceTimersByTimeAsync(0);
    results();
    await vi.advanceTimersByTimeAsync(0);
    fixture.detectChanges();
  });

  afterEach(() => {
    try { fixture.destroy(); http.verify(); }
    finally { vi.useRealTimers(); TestBed.resetTestingModule(); }
  });

  it('actualise les résultats puis arrête les appels à la fin', async () => {
    expect(fixture.componentInstance.results()[0].rank).toBe(1);
    await vi.advanceTimersByTimeAsync(2000);
    http.expectOne(req => req.url === '/api/v1/matching-runs').flush({ items: [run(200, 'completed')] });
    await vi.advanceTimersByTimeAsync(0);
    results();
    await vi.advanceTimersByTimeAsync(0);
    fixture.detectChanges();
    expect(fixture.componentInstance.selectedRun()?.status).toBe('completed');
    expect(fixture.nativeElement.textContent).toContain('Classement des CV pour le poste');
    await vi.advanceTimersByTimeAsync(4000);
    http.expectNone(req => req.url === '/api/v1/matching-runs');
  });

  it('affiche le rang et le pourcentage pondéré fournis par le serveur', () => {
    const text=fixture.nativeElement.textContent;
    expect(text).toContain('#1');expect(text).toContain('81,25 %');
    expect(text).toContain('#2');expect(text).toContain('43,75 %');
    expect(text).toContain('80 % du poids du poste');
    expect(fixture.componentInstance.matchingDisplay({...ranked[0],matching_percentage:0})).toBe('0 %');
    expect(fixture.componentInstance.matchingDisplay({...ranked[0],matching_percentage:null})).toBe('Non calculable');
  });

  it('ignore les résultats d’une campagne quittée et empêche les doubles lancements', async () => {
    await fixture.componentInstance.launch();
    http.expectNone(req => req.method === 'POST');
    const old = fixture.componentInstance.loadResults();
    const oldRequest = http.expectOne(req => req.url.endsWith('/results'));
    fixture.componentInstance.campaignId = 'campaign-b';
    fixture.componentInstance.selectionChanged();
    http.expectOne(req => req.url === '/api/v1/matching-runs').flush({ items: [run(0, 'queued', 'campaign-b')] });
    await vi.advanceTimersByTimeAsync(0);
    results();
    oldRequest.flush({ items: [{ id: 'ancien-résultat' }], total: 1 });
    await old;
    expect(fixture.componentInstance.results()).toEqual(ranked);
    expect(fixture.componentInstance.selectedRunId()).toBe('run-campaign-b');
  });
});
