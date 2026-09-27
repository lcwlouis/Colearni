import { describe, expect, it } from 'vitest';
import { createMockDeskAdapter } from './mockDeskAdapter';

describe('mock desk adapter', () => {
  it('loads the synthetic desk', async () => {
    const desk = await createMockDeskAdapter().loadDesk('desk-demo');
    expect(desk.deskId).toBe('desk-demo');
    expect(desk.label).toMatch(/SYNTHETIC/);
  });

  it('rejects unknown desks', async () => {
    await expect(createMockDeskAdapter().loadDesk('nope')).rejects.toThrow(/Unknown desk/);
  });

  it('returns copies so callers cannot mutate adapter state', async () => {
    const adapter = createMockDeskAdapter();
    const first = await adapter.loadDesk('desk-demo');
    first.notes[0]!.blocks[0]!.text = 'tampered';
    const second = await adapter.loadDesk('desk-demo');
    expect(second.notes[0]!.blocks[0]!.text).not.toBe('tampered');
  });

  it('refuses to start from invalid data', () => {
    expect(() => createMockDeskAdapter({ deskId: 'x' })).toThrow();
  });
});
