import type { Meta, StoryObj } from '@storybook/react-vite';
import { expect, userEvent, within } from 'storybook/test';
import { ToolingSmoke } from './ToolingSmoke';

const meta = {
  title: 'Tooling/Smoke',
  component: ToolingSmoke,
} satisfies Meta<typeof ToolingSmoke>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Interaction: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('Pressed 0 times')).toBeVisible();
    await userEvent.click(canvas.getByRole('button', { name: 'Press' }));
    await expect(canvas.getByText('Pressed 1 times')).toBeVisible();
  },
};
