/**
 * Normalises TeX delimiters so `remark-math` can render them.
 *
 * Converts `\\(...\\)` to `$...$` and `\\[...\\]` to `$$...$$`, while leaving
 * fenced code blocks and inline code spans untouched. Kept dependency-free so it
 * can be reused by both the tutor renderer and the quiz renderer without pulling
 * in the heavy assistant-ui markdown module.
 */
export function preprocessTutorMarkdown(text: string): string {
  const chunks = text.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
  return chunks
    .map((chunk) => {
      if (chunk.startsWith("`")) {
        return chunk;
      }
      return chunk
        .replace(/\\\[([\s\S]*?)\\\]/g, (_match, math: string) => `$$${math}$$`)
        .replace(/\\\(([\s\S]*?)\\\)/g, (_match, math: string) => `$${math}$`);
    })
    .join("");
}
