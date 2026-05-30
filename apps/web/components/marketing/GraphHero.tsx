const NODES = [
  { id: "a", x: 60, y: 150, r: 13, c: "#10b981" },
  { id: "b", x: 150, y: 70, r: 11, c: "#10b981" },
  { id: "c", x: 165, y: 220, r: 11, c: "#2563eb" },
  { id: "d", x: 270, y: 130, r: 15, c: "#2563eb" },
  { id: "e", x: 300, y: 250, r: 10, c: "#f59e0b" },
  { id: "f", x: 390, y: 80, r: 10, c: "#94a3b8" },
  { id: "g", x: 410, y: 200, r: 12, c: "#94a3b8" },
];

const EDGES: Array<[string, string]> = [
  ["a", "b"],
  ["a", "c"],
  ["b", "d"],
  ["c", "d"],
  ["c", "e"],
  ["d", "f"],
  ["d", "g"],
  ["e", "g"],
];

function node(id: string) {
  const n = NODES.find((x) => x.id === id);
  if (!n) throw new Error(`unknown node ${id}`);
  return n;
}

export function GraphHero({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 470 300"
      className={className}
      role="img"
      aria-label="A concept graph lighting up from mastered to new"
    >
      <g stroke="currentColor" strokeWidth="1.5" opacity="0.35">
        {EDGES.map(([from, to], i) => {
          const a = node(from);
          const b = node(to);
          return (
            <line
              key={`${from}-${to}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              pathLength={1}
              strokeDasharray="1"
              style={{
                animation: `mk-edge-draw 0.9s ease forwards`,
                animationDelay: `${0.15 * i}s`,
                strokeDashoffset: 1,
              }}
            />
          );
        })}
      </g>
      {NODES.map((n, i) => (
        <circle
          key={n.id}
          cx={n.x}
          cy={n.y}
          r={n.r}
          fill={n.c}
          style={{
            animation: `mk-node-pulse 3.2s ease-in-out infinite`,
            animationDelay: `${0.2 * i}s`,
          }}
        />
      ))}
    </svg>
  );
}
