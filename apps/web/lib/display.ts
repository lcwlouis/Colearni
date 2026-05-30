/**
 * Display-only formatting helpers.
 *
 * These functions transform raw enum/string values into human-friendly labels
 * for the UI. They must NEVER be used to change values sent to the API — only
 * what is rendered to the user.
 */

/** Title-cases a single token or snake_case/kebab-case string. */
export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .trim()
    .split(/\s+/)
    .map((word) =>
      word.length === 0
        ? word
        : word[0].toUpperCase() + word.slice(1).toLowerCase(),
    )
    .join(" ");
}

/** Display label for a Bloom / target-depth level, e.g. "apply" -> "Apply". */
export function formatBloomLevel(level: string): string {
  return titleCase(level);
}

/** Display label for a graph-size option, e.g. 40 -> "Up to 40 concepts". */
export function formatGraphSize(maxNodes: number): string {
  return `Up to ${maxNodes} concepts`;
}
