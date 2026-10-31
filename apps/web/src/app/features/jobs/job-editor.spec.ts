import { describe, expect, it, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { JobEditor } from './job-editor';

describe('Liens exacts des critères au référentiel', () => {
  it('affiche la compétence résolue sans modification non enregistrée du poste', async () => {
    TestBed.configureTestingModule({imports:[JobEditor],providers:[provideHttpClient(),provideHttpClientTesting(),provideRouter([]),
      {provide:ActivatedRoute,useValue:{snapshot:{paramMap:convertToParamMap({id:'job-test'})}}},
    ]});
    const fixture=TestBed.createComponent(JobEditor);const http=TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne('/api/v1/skills?limit=100').flush({items:[{id:'skill-python',code:'python',label_fr:'Python',label_en:'Python'}]});
    http.expectOne('/api/v1/jobs/job-test').flush({id:'job-test',title:'Développeur backend',description:'Poste fictif de test backend',criteria_version:3,criteria_confirmed_at:'2026-10-31T10:00:00',requirements:[
      {id:'r1',code:'BACKEND_REQ_1',label:'Python',category:'skill',required:true,weight:3,justification:'Développement backend',skill_ref:null,resolved_skill_id:'skill-python'},
      {id:'r2',code:'BACKEND_REQ_2',label:'Redis',category:'skill',required:false,weight:1,justification:'Cache des résultats',skill_ref:null,resolved_skill_id:null},
    ]});
    await vi.waitFor(()=>expect(fixture.componentInstance.loading()).toBe(false));
    fixture.detectChanges();await fixture.whenStable();
    expect(fixture.componentInstance.requirements()[0].skill_ref).toBe('skill-python');
    expect(fixture.componentInstance.job()?.requirements[0].skill_ref).toBeNull();
    expect(fixture.componentInstance.unmappedSkills()).toBe(1);
    expect(fixture.componentInstance.canLeave()).toBe(true);
    const option=Array.from(fixture.nativeElement.querySelectorAll('option') as NodeListOf<HTMLOptionElement>)
      .find(option=>option.textContent?.includes('Python'));
    expect(option?.selected).toBe(true);
    fixture.destroy();http.verify();
  });
});
