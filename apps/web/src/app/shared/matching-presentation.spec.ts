import { describe, expect, it } from 'vitest';
import { coverageScope, criterionKind, criterionReason, criterionStatus } from './matching-presentation';

describe('Transparence des scores et preuves', () => {
  it('ne transforme pas une couverture non évaluable en score zéro', () => {
    expect(coverageScope({ summary: {assessable_weight_percent: 0, evaluable_subset_coverage: null} }))
      .toEqual({assessable_weight_percent: 0, evaluable_subset_coverage: null});
  });
  it('rejette les données de couverture invalides', () => {
    expect(coverageScope({summary:{assessable_weight_percent: Number.NaN}})).toBeNull();
    expect(coverageScope(undefined)).toBeNull();
  });
  it('sépare mentions et éléments devant être vérifiés', () => {
    expect(criterionKind('documented_mention')).toBe('documented');
    expect(criterionKind('manual_review_required')).toBe('review');
    expect(criterionKind('not_found')).toBe('not_found');
    expect(criterionStatus('manual_review_required')).toContain('Examen humain');
    expect(criterionReason('AMBIGUOUS_MENTION')).toContain('confirmer');
  });
});
