import { describe, expect, it } from 'vitest';
import fixture from '../../fixtures/paper-session.synthetic.json';
import {
  ValidationError,
  parseDeskCard,
  parseDeskSnapshot,
  parseJsonValue,
  parseLearnerNote,
} from './validate';

const clone = <T>(v: T): T => structuredClone(v);

describe('synthetic fixture against the contract', () => {
  it('is labelled synthetic and validates', () => {
    expect(fixture.label).toMatch(/SYNTHETIC/);
    expect(fixture.source.notARealUpload).toBe(true);
    const snap = parseDeskSnapshot(fixture);
    expect(snap.cards.map((c) => c.id)).toEqual(['card-source', 'card-example', 'card-plot']);
    expect(snap.notes.map((n) => n.tutorReadAccess)).toEqual(['shared', 'private']);
  });

  it('expected context preview contains no private note id or text', () => {
    const privateNotes = fixture.notes.filter((n) => n.tutorReadAccess === 'private');
    const serialised = JSON.stringify(fixture.expectedContextPreview);
    expect(privateNotes.length).toBeGreaterThan(0);
    for (const note of privateNotes) {
      expect(serialised).not.toContain(note.id);
      for (const block of note.blocks) expect(serialised).not.toContain(block.text);
    }
  });

  it('expected context excerpts are marked untrusted and match the shared note', () => {
    const note = parseLearnerNote(fixture.notes[0]);
    const preview = fixture.expectedContextPreview;
    expect(preview.index.map((e) => e.noteId)).toEqual([note.id]);
    for (const excerpt of preview.recentExcerpts) {
      expect(excerpt.trust).toBe('untrusted_task_data');
      expect(excerpt.toRevision).toBe(note.revision);
      for (const block of excerpt.blocks) {
        expect(note.blocks.find((b) => b.id === block.id)?.text).toBe(block.text);
      }
    }
  });
});

describe('runtime validation rejects bad data', () => {
  it('rejects duplicate card ids', () => {
    const bad = clone(fixture);
    bad.cards[1]!.id = bad.cards[0]!.id;
    expect(() => parseDeskSnapshot(bad)).toThrow(/duplicate id/);
  });

  it('rejects a card from another desk', () => {
    const bad = clone(fixture);
    bad.cards[0]!.deskId = 'other-desk';
    expect(() => parseDeskSnapshot(bad)).toThrow(ValidationError);
  });

  it('rejects non-positive or fractional revisions', () => {
    for (const rev of [0, -1, 1.5, '2']) {
      const note = { ...clone(fixture.notes[0]!), revision: rev };
      expect(() => parseLearnerNote(note)).toThrow(/revision/);
    }
  });

  it('rejects unknown origins, sharing values and contract versions', () => {
    const note = clone(fixture.notes[0]!);
    note.blocks[0]!.provenance.origin = 'agent';
    expect(() => parseLearnerNote(note)).toThrow(/origin/);
    expect(() => parseLearnerNote({ ...clone(fixture.notes[0]!), tutorReadAccess: 'public' })).toThrow(
      /tutorReadAccess/,
    );
    expect(() => parseDeskCard({ ...clone(fixture.cards[0]!), contractVersion: '2' })).toThrow(
      /contract version/,
    );
  });

  it('rejects plugin version ranges and unknown body kinds', () => {
    const card = clone(fixture.cards[1]!) as Record<string, unknown> & typeof fixture.cards[1];
    (card.body as { plugin: { version: string } }).plugin.version = '^1.0.0';
    expect(() => parseDeskCard(card)).toThrow(/exact/);
    expect(() => parseDeskCard({ ...clone(fixture.cards[0]!), body: { kind: 'html', html: '<b>' } })).toThrow(
      /body kind/,
    );
  });

  it('accepts only plain JSON as plugin data', () => {
    expect(parseJsonValue({ a: [1, 'x', null, true] }, 'v')).toEqual({ a: [1, 'x', null, true] });
    expect(() => parseJsonValue({ f: () => 1 }, 'v')).toThrow(/plain JSON/);
    expect(() => parseJsonValue(Number.NaN, 'v')).toThrow(/finite/);
    expect(() => parseJsonValue(new Date(), 'v')).toThrow(/plain JSON/);
  });
});
