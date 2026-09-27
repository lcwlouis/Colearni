import type { DeskSnapshot } from '../domain/validate';

/** Boundary between UI and data. A future HTTP adapter implements the same interface. */
export interface DeskAdapter {
  loadDesk(deskId: string): Promise<DeskSnapshot>;
}
