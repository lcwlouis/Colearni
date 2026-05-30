export const NAV_LINKS = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/pedagogy", label: "Pedagogy" },
  { href: "/pricing", label: "Pricing" },
  { href: "/contact", label: "Contact" },
] as const;

export const CONTACT_EMAIL = "hello@colearni.app";
export const GITHUB_URL = "https://github.com/colearni";

export const HOW_IT_WORKS_STEPS = [
  {
    n: "01",
    title: "Name what you want to learn",
    body: "Describe a topic and a goal. CoLearni turns it into a Trail — a learning project scoped to where you are now.",
  },
  {
    n: "02",
    title: "A concept graph is built",
    body: "Your Trail becomes a prerequisite graph, from umbrella ideas down to granular concepts, so the order makes sense.",
  },
  {
    n: "03",
    title: "Click a concept, meet the tutor",
    body: "Open any concept and a Socratic tutor works with you — questions first, explanations when you need them.",
  },
  {
    n: "04",
    title: "Level up with a quiz",
    body: "When you are ready, a short level-up quiz checks real understanding instead of recognition.",
  },
  {
    n: "05",
    title: "Watch mastery update",
    body: "The graph colours in as you progress — mastered, learning, needs review — so you always know what is next.",
  },
] as const;

export const PEDAGOGY_SECTIONS = [
  {
    eyebrow: "The depth dial",
    title: "Bloom's Taxonomy as your target depth",
    body: `Every Trail has a target depth — from remembering and understanding up to analysing, evaluating, and creating. CoLearni aims its questions and quizzes at the level you chose, so “learn it” means the right thing for your goal.`,
  },
  {
    eyebrow: "How the tutor talks",
    title: "Socratic questioning",
    body: "The tutor leads with questions that surface what you already believe, then nudges you to refine it. You do the thinking; it provides the scaffolding and steps in with direct explanation only when you are genuinely stuck.",
  },
  {
    eyebrow: "Don't move on too early",
    title: "Bloom mastery learning",
    body: "Concepts are gated by mastery, not by time spent. You advance when you can actually use an idea — and the system routes you back to weak spots before they compound.",
  },
  {
    eyebrow: "Make it stick",
    title: "Active recall & retrieval practice",
    body: "Level-up quizzes ask you to retrieve and apply, not just recognise. Pulling knowledge out strengthens it far more than reading it again.",
  },
  {
    eyebrow: "Build on firm ground",
    title: "Scaffolding along a prerequisite graph",
    body: "New concepts are introduced only once their prerequisites are in place. The graph keeps you on solid footing instead of dropping you into the deep end.",
  },
] as const;

export const PRICING_TIERS = [
  {
    name: "Self-host / Open source",
    pitch: "Run CoLearni on your own machine or server. Bring your own LLM key.",
    points: ["Local-first", "Your data stays yours", "Source-available"],
  },
  {
    name: "Free hosted",
    pitch: "A hosted tier so you can start learning without setting anything up.",
    points: ["Nothing to install", "Core learning loop", "Limits TBC"],
  },
  {
    name: "Paid hosted",
    pitch: "More capacity and hosted conveniences for serious, ongoing learning.",
    points: ["Higher limits", "Hosted LLM keys", "Pricing TBC"],
  },
] as const;
