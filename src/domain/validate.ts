/**
 * Minimal runtime validation for the draft contract (contracts/desk-contracts.ts).
 * TypeScript types do not check data at runtime; these functions do, for the
 * fields P0/P1 rely on. Not an authorisation boundary.
 */
import type {
  DeskCard,
  JsonValue,
  LearnerNote,
  Origin,
  Provenance,
  SourceRef,
  TextBlock,
} from '../../contracts/desk-contracts';

export class ValidationError extends Error {
  constructor(
    readonly path: string,
    message: string,
  ) {
    super(`${path}: ${message}`);
    this.name = 'ValidationError';
  }
}

type Rec = Record<string, unknown>;

const ORIGINS: readonly Origin[] = ['learner', 'tutor', 'source'];

function record(value: unknown, path: string): Rec {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new ValidationError(path, 'expected an object');
  }
  return value as Rec;
}

function str(value: unknown, path: string): string {
  if (typeof value !== 'string' || value.length === 0) {
    throw new ValidationError(path, 'expected a non-empty string');
  }
  return value;
}

function revision(value: unknown, path: string): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 1) {
    throw new ValidationError(path, 'expected a positive integer revision');
  }
  return value;
}

function array(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) throw new ValidationError(path, 'expected an array');
  return value;
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[], path: string): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) {
    throw new ValidationError(path, `expected one of ${allowed.join(', ')}`);
  }
  return value as T;
}

export function parseSourceRef(value: unknown, path: string): SourceRef {
  const r = record(value, path);
  return {
    sourceId: str(r.sourceId, `${path}.sourceId`),
    sourceRevision: revision(r.sourceRevision, `${path}.sourceRevision`),
    locator: str(r.locator, `${path}.locator`),
    label: str(r.label, `${path}.label`),
  };
}

export function parseProvenance(value: unknown, path: string): Provenance {
  const r = record(value, path);
  const provenance: Provenance = {
    origin: oneOf(r.origin, ORIGINS, `${path}.origin`),
    sourceRefs: array(r.sourceRefs, `${path}.sourceRefs`).map((ref, i) =>
      parseSourceRef(ref, `${path}.sourceRefs[${i}]`),
    ),
  };
  if (r.acceptedByLearnerId !== undefined) {
    provenance.acceptedByLearnerId = str(r.acceptedByLearnerId, `${path}.acceptedByLearnerId`);
  }
  return provenance;
}

export function parseTextBlock(value: unknown, path: string): TextBlock {
  const r = record(value, path);
  if (typeof r.text !== 'string') throw new ValidationError(`${path}.text`, 'expected a string');
  return {
    id: str(r.id, `${path}.id`),
    text: r.text,
    provenance: parseProvenance(r.provenance, `${path}.provenance`),
  };
}

function uniqueIds<T extends { id: string }>(items: T[], path: string): T[] {
  const seen = new Set<string>();
  for (const item of items) {
    if (seen.has(item.id)) throw new ValidationError(path, `duplicate id "${item.id}"`);
    seen.add(item.id);
  }
  return items;
}

export function parseLearnerNote(value: unknown, path = 'note'): LearnerNote {
  const r = record(value, path);
  return {
    id: str(r.id, `${path}.id`),
    deskId: str(r.deskId, `${path}.deskId`),
    revision: revision(r.revision, `${path}.revision`),
    ownerId: str(r.ownerId, `${path}.ownerId`),
    title: str(r.title, `${path}.title`),
    tutorReadAccess: oneOf(r.tutorReadAccess, ['shared', 'private'] as const, `${path}.tutorReadAccess`),
    blocks: uniqueIds(
      array(r.blocks, `${path}.blocks`).map((b, i) => parseTextBlock(b, `${path}.blocks[${i}]`)),
      `${path}.blocks`,
    ),
    updatedAt: str(r.updatedAt, `${path}.updatedAt`),
  };
}

/** Accepts only plain JSON data: no functions, undefined, non-finite numbers, or class instances. */
export function parseJsonValue(value: unknown, path: string, depth = 0): JsonValue {
  if (depth > 32) throw new ValidationError(path, 'JSON value nested too deeply');
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new ValidationError(path, 'expected a finite number');
    return value;
  }
  if (Array.isArray(value)) return value.map((v, i) => parseJsonValue(v, `${path}[${i}]`, depth + 1));
  if (typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype) {
    const out: { [key: string]: JsonValue } = {};
    for (const [k, v] of Object.entries(value)) out[k] = parseJsonValue(v, `${path}.${k}`, depth + 1);
    return out;
  }
  throw new ValidationError(path, 'expected plain JSON data');
}

/** Plugin id + exact version (not a range). Bodies stay opaque JSON until P3. */
const EXACT_VERSION = /^\d+\.\d+\.\d+$/;

export function parseDeskCard(value: unknown, path = 'card'): DeskCard {
  const r = record(value, path);
  if (r.contractVersion !== '1') {
    throw new ValidationError(`${path}.contractVersion`, 'unsupported contract version');
  }
  const body = record(r.body, `${path}.body`);
  let parsedBody: DeskCard['body'];
  if (body.kind === 'text') {
    parsedBody = {
      kind: 'text',
      blocks: uniqueIds(
        array(body.blocks, `${path}.body.blocks`).map((b, i) =>
          parseTextBlock(b, `${path}.body.blocks[${i}]`),
        ),
        `${path}.body.blocks`,
      ),
    };
  } else if (body.kind === 'plugin') {
    const plugin = record(body.plugin, `${path}.body.plugin`);
    const version = str(plugin.version, `${path}.body.plugin.version`);
    if (!EXACT_VERSION.test(version)) {
      throw new ValidationError(`${path}.body.plugin.version`, 'expected an exact x.y.z version');
    }
    parsedBody = {
      kind: 'plugin',
      plugin: { id: str(plugin.id, `${path}.body.plugin.id`), version },
      input: parseJsonValue(body.input, `${path}.body.input`),
      savedState: parseJsonValue(body.savedState, `${path}.body.savedState`),
    };
  } else {
    throw new ValidationError(`${path}.body.kind`, 'unknown card body kind');
  }
  return {
    id: str(r.id, `${path}.id`),
    deskId: str(r.deskId, `${path}.deskId`),
    revision: revision(r.revision, `${path}.revision`),
    contractVersion: '1',
    title: str(r.title, `${path}.title`),
    provenance: parseProvenance(r.provenance, `${path}.provenance`),
    body: parsedBody,
    textFallback: str(r.textFallback, `${path}.textFallback`),
  };
}

export interface DeskSnapshot {
  deskId: string;
  label: string;
  notes: LearnerNote[];
  cards: DeskCard[];
}

/** Validates the fixture shape the mock adapter serves. */
export function parseDeskSnapshot(value: unknown): DeskSnapshot {
  const r = record(value, 'fixture');
  const deskId = str(r.deskId, 'fixture.deskId');
  const notes = uniqueIds(
    array(r.notes, 'fixture.notes').map((n, i) => parseLearnerNote(n, `fixture.notes[${i}]`)),
    'fixture.notes',
  );
  const cards = uniqueIds(
    array(r.cards, 'fixture.cards').map((c, i) => parseDeskCard(c, `fixture.cards[${i}]`)),
    'fixture.cards',
  );
  for (const item of [...notes, ...cards]) {
    if (item.deskId !== deskId) {
      throw new ValidationError(`fixture.${item.id}`, 'belongs to a different desk');
    }
  }
  return { deskId, label: str(r.label, 'fixture.label'), notes, cards };
}
