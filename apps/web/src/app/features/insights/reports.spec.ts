import { afterEach, describe, expect, it, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { Reports } from './reports';

describe('Export du classement sélectionné', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('conserve la campagne et l’analyse sélectionnées dans la requête d’export', async () => {
    TestBed.configureTestingModule({ imports: [Reports], providers: [
      provideHttpClient(), provideHttpClientTesting(),
      {provide:ActivatedRoute,useValue:{snapshot:{queryParamMap:convertToParamMap({campaign:'campaign-test',run:'run-test'})}}},
    ] });
    const fixture=TestBed.createComponent(Reports);
    const http=TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne(req=>req.url==='/api/v1/campaigns').flush({items:[{id:'campaign-test',name:'Campagne fictive',status:'active'}]});
    http.expectOne(req=>req.url==='/api/v1/reports/history').flush({items:[]});
    await vi.waitFor(()=>expect(fixture.componentInstance.loading()).toBe(false));
    const task=fixture.componentInstance.download();
    const request=http.expectOne(req=>req.url==='/api/v1/reports/campaigns/campaign-test');
    expect(request.request.params.get('run_id')).toBe('run-test');
    expect(request.request.params.get('format')).toBe('pdf');
    expect(request.request.params.has('progress')).toBe(false);
    request.flush(new Blob(),{status:503,statusText:'Unavailable'});
    await task;
    fixture.destroy();http.verify();
  });
});
