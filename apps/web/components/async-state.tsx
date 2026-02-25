type Props = { loading: boolean; error: string | null; empty: boolean; emptyLabel?: string };

export function AsyncState({ loading, error, empty, emptyLabel = "No data yet." }: Props) {
  if (loading) return <p className="status loading">Loading...</p>;
  if (error) return <p className="status error">API error: {error}</p>;
  if (empty) return <p className="status empty">{emptyLabel}</p>;
  return null;
}
