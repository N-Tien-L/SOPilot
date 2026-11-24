import { describe, expect, it } from 'vitest';
import { FAMILIES, OTHER_FAMILY_NOTES, ruleLabel } from './report-labels';

describe('ruleLabel', () => {
  it.each(['HEADING_TREE', 'ARTICLE_UNIT', 'MERGE_SHORT', 'STEP_ROW', 'PACK', 'PREFIX'])(
    'has a title and a detail for %s',
    (id) => {
      const label = ruleLabel(id);
      expect(label.title.length).toBeGreaterThan(0);
      expect(label.detail.length).toBeGreaterThan(0);
    },
  );

  it('titles the article rule by heading', () => {
    expect(ruleLabel('ARTICLE_UNIT').title).toBe('One chunk per article heading');
  });

  it('falls back to the id for an unknown rule', () => {
    expect(ruleLabel('SOMETHING_NEW')).toEqual({ title: 'SOMETHING_NEW', detail: '' });
  });
});

describe('OTHER_FAMILY_NOTES', () => {
  it('has a note for every family', () => {
    for (const f of FAMILIES) expect(OTHER_FAMILY_NOTES[f.id].length).toBeGreaterThan(0);
  });

  it('does not claim legal articles are never merged', () => {
    expect(OTHER_FAMILY_NOTES.LEGAL_ARTICLES).not.toContain('never merged');
  });
});
