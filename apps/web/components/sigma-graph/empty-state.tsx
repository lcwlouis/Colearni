import styles from "./empty-state.module.css";

export function EmptyState() {
  return (
    <div className={styles.wrapper}>
      <span className={styles.icon}>Graph</span>
      <p className={styles.text}>
        No concepts yet — ingest a document to build your knowledge graph
      </p>
      <a className={styles.link} href="/sources">
        Go to Sources
      </a>
    </div>
  );
}
