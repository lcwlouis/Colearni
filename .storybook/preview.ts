import type { Preview } from '@storybook/react-vite';
// Same CSS entry as the app, so both surfaces share one style source.
import '../src/styles/index.css';

const preview: Preview = {
  parameters: {
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    // Accessibility violations fail story tests rather than only warning.
    a11y: { test: 'error' },
  },
};

export default preview;
