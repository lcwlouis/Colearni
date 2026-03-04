import styles from "./graph-skeleton.module.css";

const NODES = [
  { cx: 20, cy: 30, r: 4 },
  { cx: 45, cy: 18, r: 3 },
  { cx: 70, cy: 35, r: 5 },
  { cx: 30, cy: 60, r: 3.5 },
  { cx: 55, cy: 55, r: 4 },
  { cx: 80, cy: 65, r: 3 },
  { cx: 15, cy: 78, r: 3 },
  { cx: 50, cy: 80, r: 4.5 },
  { cx: 75, cy: 85, r: 3 },
];

const EDGES: [number, number][] = [
  [0, 1],
  [1, 2],
  [0, 3],
  [2, 4],
  [3, 4],
  [4, 5],
  [3, 6],
  [6, 7],
];

export function GraphSkeleton() {
  return (
    <div className={styles.wrapper}>
      <svg className={styles.svg} viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
        <g className={styles.shimmer}>
          {EDGES.map(([a, b], i) => (
            <line
              key={`e${i}`}
              className={styles.line}
              x1={NODES[a].cx}
              y1={NODES[a].cy}
              x2={NODES[b].cx}
              y2={NODES[b].cy}
            />
          ))}
          {NODES.map((n, i) => (
            <circle key={`n${i}`} className={styles.shape} cx={n.cx} cy={n.cy} r={n.r} />
          ))}
        </g>
      </svg>
    </div>
  );
}
