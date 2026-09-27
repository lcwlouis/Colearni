import { useState } from 'react';

/**
 * Tooling smoke check only: proves React, Tailwind and Storybook are wired.
 * Not a Desk design; learner-facing components wait for the visual gate (P1).
 */
export function ToolingSmoke() {
  const [count, setCount] = useState(0);
  return (
    <section aria-labelledby="smoke-heading" className="p-4">
      <h2 id="smoke-heading">Tooling smoke check</h2>
      <p>Pressed {count} times</p>
      <button type="button" className="underline" onClick={() => setCount((c) => c + 1)}>
        Press
      </button>
    </section>
  );
}
