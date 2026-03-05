/**
 * Theme-aware replacement for sigma's drawDiscNodeHover.
 * Factory returns a hover-drawing function parameterised by background/shadow
 * colors so the label highlight box updates when the theme toggles.
 */
import { drawDiscNodeLabel } from "sigma/rendering";

export function createDrawNodeHover(backgroundColor: string, shadowColor: string) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return function drawNodeHover(context: CanvasRenderingContext2D, data: any, settings: any) {
    const size = settings.labelSize;
    const font = settings.labelFont;
    const weight = settings.labelWeight;
    context.font = `${weight} ${size}px ${font}`;

    context.fillStyle = backgroundColor;
    context.shadowOffsetX = 0;
    context.shadowOffsetY = 0;
    context.shadowBlur = 8;
    context.shadowColor = shadowColor;

    const PADDING = 2;

    if (typeof data.label === "string") {
      const textWidth = context.measureText(data.label).width;
      const boxWidth = Math.round(textWidth + 5);
      const boxHeight = Math.round(size + 2 * PADDING);
      const radius = Math.max(data.size, size / 2) + PADDING;
      const angleRadian = Math.asin(boxHeight / 2 / radius);
      const xDeltaCoord = Math.sqrt(
        Math.abs(Math.pow(radius, 2) - Math.pow(boxHeight / 2, 2)),
      );

      context.beginPath();
      context.moveTo(data.x + xDeltaCoord, data.y + boxHeight / 2);
      context.lineTo(data.x + radius + boxWidth, data.y + boxHeight / 2);
      context.lineTo(data.x + radius + boxWidth, data.y - boxHeight / 2);
      context.lineTo(data.x + xDeltaCoord, data.y - boxHeight / 2);
      context.arc(data.x, data.y, radius, angleRadian, -angleRadian);
      context.closePath();
      context.fill();
    } else {
      context.beginPath();
      context.arc(data.x, data.y, data.size + PADDING, 0, Math.PI * 2);
      context.closePath();
      context.fill();
    }

    context.shadowOffsetX = 0;
    context.shadowOffsetY = 0;
    context.shadowBlur = 0;

    drawDiscNodeLabel(context, data, settings);
  };
}
