import fixture from '../../fixtures/paper-session.synthetic.json';
import { parseDeskSnapshot, type DeskSnapshot } from '../domain/validate';
import type { DeskAdapter } from './deskAdapter';

/**
 * Deterministic in-memory adapter serving the SYNTHETIC fixture only.
 * Demo data; not persistent, authenticated, or secure storage.
 */
export function createMockDeskAdapter(source: unknown = fixture): DeskAdapter {
  const snapshot = parseDeskSnapshot(source);
  return {
    async loadDesk(deskId) {
      if (deskId !== snapshot.deskId) throw new Error(`Unknown desk "${deskId}"`);
      // Callers get a copy so they cannot mutate adapter state.
      return structuredClone(snapshot) satisfies DeskSnapshot;
    },
  };
}
