import Image from "next/image";
import Link from "next/link";

const FEATURES = [
  { title: "AI Tutor", desc: "Ask questions and get grounded answers tied to your knowledge base." },
  { title: "Knowledge Graph", desc: "Visualize concepts and their relationships as you learn." },
  { title: "Adaptive Quizzes", desc: "Level-up quizzes that adjust to your mastery." },
] as const;

export function LandingPage() {
  return (
    <div className="public-entry">
      <section className="landing-hero">
        <Image
          src="/colearniTreeLogo.png"
          alt="CoLearni logo"
          width={72}
          height={72}
          className="landing-logo"
          priority
        />
        <h1 className="landing-title">Learn&nbsp;smarter with&nbsp;CoLearni</h1>
        <p className="landing-subtitle">
          An AI-powered learning workspace that turns your documents into an
          interactive knowledge graph, adaptive quizzes, and a personal tutor.
        </p>
        <div className="landing-cta-row">
          <Link href="/login" className="landing-cta-primary">
            Sign up
          </Link>
          <Link href="/login" className="landing-cta-secondary">
            Log in
          </Link>
        </div>
      </section>

      <section className="landing-features">
        {FEATURES.map((f) => (
          <div key={f.title} className="landing-feature-card">
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
