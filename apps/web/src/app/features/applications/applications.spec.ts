import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Application } from '../../shared/recruitment';
import { Applications } from './applications';

const applications: Application[] = ['a', 'b'].map(id => ({
  id, candidate_id: `candidate-${id}`, campaign_id: 'campaign-test',
  candidate_name: `Dossier de test ${id}`, campaign_name: 'Campagne de test',
  review_status: 'pending', created_at: '2026-10-30T10:00:00',
}));

describe('Ouverture et enregistrement des avis humains', () => {
  let fixture: ComponentFixture<Applications>;
  let http: HttpTestingController;
  let scrollIntoView: ReturnType<typeof vi.fn<HTMLElement['scrollIntoView']>>;
  const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView');
  const reviewUrl = (id: string) => `/api/v1/applications/${id}/reviews`;
  const history = (note: string) => [{ finding: 'reviewed', note, created_at: '2026-10-30T10:00:00' }];
  const openButtons = () => fixture.nativeElement.querySelectorAll('.record-action') as NodeListOf<HTMLButtonElement>;

  beforeEach(async () => {
    scrollIntoView = vi.fn<HTMLElement['scrollIntoView']>();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView });
    TestBed.configureTestingModule({
      imports: [Applications], providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    fixture = TestBed.createComponent(Applications);
    http = TestBed.inject(HttpTestingController);
    fixture.autoDetectChanges();
    http.expectOne(request => request.url === '/api/v1/applications').flush({ items: applications, total: 2 });
    http.expectOne('/api/v1/candidates?limit=100').flush({ items: [] });
    http.expectOne('/api/v1/campaigns?limit=100').flush({ items: [] });
    await vi.waitFor(() => expect(fixture.componentInstance.loading()).toBe(false));
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => {
    http.verify();
    if (originalScroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', originalScroll);
    else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView');
    vi.restoreAllMocks();
  });

  it('rend le formulaire visible et place le focus sur le dossier dès le clic', async () => {
    const trigger = openButtons()[0];
    trigger.click();
    fixture.detectChanges();
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'start', behavior: 'instant' });
    expect(document.activeElement?.id).toBe('application-review-title');
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(fixture.nativeElement.textContent).toContain('Chargement des avis…');
    http.expectOne(reviewUrl('a')).flush([]);
    await fixture.whenStable();
    const note = fixture.nativeElement.querySelector('#review-note') as HTMLTextAreaElement;
    expect(note.labels?.[0].textContent).toBe('Note factuelle du recruteur');
    expect(note.maxLength).toBe(4000);
    fixture.nativeElement.querySelector('#application-review button[type="button"]').click();
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('#application-review')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('ignore une réponse ancienne lorsqu’un autre dossier a été ouvert', async () => {
    const first = fixture.componentInstance.select(applications[0]);
    const requestA = http.expectOne(reviewUrl('a'));
    const second = fixture.componentInstance.select(applications[1]);
    const requestB = http.expectOne(reviewUrl('b'));
    requestA.flush(history('Avis du dossier A'));
    await first;
    expect(fixture.componentInstance.pastReviews()).toEqual([]);
    expect(fixture.componentInstance.reviewsLoading()).toBe(true);
    requestB.flush(history('Avis du dossier B'));
    await second;
    expect(fixture.componentInstance.pastReviews()[0].note).toBe('Avis du dossier B');
    expect(fixture.componentInstance.reviewsLoading()).toBe(false);
  });

  it('affiche l’erreur d’historique dans le formulaire et permet de réessayer', async () => {
    openButtons()[0].click();
    http.expectOne(reviewUrl('a')).flush({}, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    const form = fixture.nativeElement.querySelector('#application-review') as HTMLFormElement;
    expect(form.querySelector('[role="alert"]')).not.toBeNull();
    const retry = Array.from(form.querySelectorAll('button')).find(button => button.textContent?.trim() === 'Réessayer');
    expect(retry).toBeDefined();
    retry!.click();
    http.expectOne(reviewUrl('a')).flush(history('Avis retrouvé'));
    await fixture.whenStable();
    expect(form.textContent).toContain('Avis retrouvé');
    expect(form.querySelector('[role="alert"]')).toBeNull();
  });

  it('conserve la note après un échec et empêche les doubles enregistrements', async () => {
    const opened = fixture.componentInstance.select(applications[0]);
    http.expectOne(reviewUrl('a')).flush([]);
    await opened;
    fixture.componentInstance.note = '  Observation factuelle de test  ';
    const failed = fixture.componentInstance.review();
    const request = http.expectOne(reviewUrl('a'));
    expect(request.request.body).toEqual({ finding: 'reviewed', note: 'Observation factuelle de test' });
    await fixture.componentInstance.review();
    http.expectNone(reviewUrl('a'));
    request.flush({}, { status: 503, statusText: 'Unavailable' });
    await failed;
    await fixture.whenStable();
    expect(fixture.componentInstance.selected()?.id).toBe('a');
    expect(fixture.componentInstance.note).toContain('Observation factuelle de test');
    expect(fixture.nativeElement.querySelector('#application-review [role="alert"]')).not.toBeNull();

    const saved = fixture.componentInstance.review();
    http.expectOne(reviewUrl('a')).flush({ id: 'review-test' });
    await Promise.resolve();
    http.expectOne(request => request.url === '/api/v1/applications').flush({ items: applications, total: 2 });
    http.expectOne('/api/v1/candidates?limit=100').flush({ items: [] });
    http.expectOne('/api/v1/campaigns?limit=100').flush({ items: [] });
    await saved;
    await fixture.whenStable();
    expect(fixture.componentInstance.selected()).toBeNull();
    expect(fixture.nativeElement.querySelector('[role="status"]').textContent).toContain('Avis humain enregistré');
  });
});
