import { ArtifactFrame } from "@/components/artifacts/ArtifactFrame";
import { ArtifactTextFallback } from "@/components/artifacts/ArtifactTextFallback";
import type { ArtifactEnvelope, ComparisonCriterion } from "@/lib/artifacts";

// Read-only `comparison_card` template: a table whose columns are the compared
// `items` and whose rows are `criteria` (a row label plus one cell per item).
// Guards against missing data or a `values`/`items` length mismatch by
// degrading to the envelope's `text_fallback`.

function isValidCriterion(
  value: unknown,
  itemCount: number,
): value is ComparisonCriterion {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const criterion = value as Record<string, unknown>;
  return (
    typeof criterion.label === "string" &&
    Array.isArray(criterion.values) &&
    criterion.values.length === itemCount &&
    criterion.values.every((v) => typeof v === "string")
  );
}

export function ComparisonCard({ envelope }: { envelope: ArtifactEnvelope }) {
  const data = envelope.data as unknown as
    | Record<string, unknown>
    | null
    | undefined;
  const items = data?.items;
  const criteria = data?.criteria;

  const isValid =
    Array.isArray(items) &&
    items.length > 0 &&
    items.every((item) => typeof item === "string") &&
    Array.isArray(criteria) &&
    criteria.length > 0 &&
    criteria.every((criterion) => isValidCriterion(criterion, items.length));

  if (!isValid) {
    return <ArtifactTextFallback text={envelope.text_fallback} />;
  }

  const columns = items as string[];
  const rows = criteria as ComparisonCriterion[];

  return (
    <ArtifactFrame
      title={envelope.title}
      caption={envelope.caption}
      testId="artifact-comparison-card"
    >
      <div className="-mx-4 overflow-x-auto px-4">
        <table className="w-full min-w-max border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-700">
              <th className="py-2 pr-3 align-bottom text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                <span className="sr-only">Criteria</span>
              </th>
              {columns.map((item, index) => (
                <th
                  key={index}
                  scope="col"
                  className="px-3 py-2 align-bottom font-semibold text-slate-900 dark:text-slate-100"
                >
                  {item}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="border-b border-slate-100 last:border-0 dark:border-slate-800"
              >
                <th
                  scope="row"
                  className="py-2 pr-3 align-top font-medium text-slate-700 dark:text-slate-300"
                >
                  {row.label}
                </th>
                {row.values.map((value, cellIndex) => (
                  <td
                    key={cellIndex}
                    className="px-3 py-2 align-top text-slate-700 dark:text-slate-300"
                  >
                    {value}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ArtifactFrame>
  );
}
