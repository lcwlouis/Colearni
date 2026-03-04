# Suggestions for a Smarter, Agentic Colearni App

This document outlines future ideas to make the Colearni platform more autonomous, intelligent, and proactive. These suggestions are for conceptual consideration and have not yet been implemented.

### 1. Proactive Knowledge Graph Curation
Instead of only extracting a knowledge graph during ingestion, background agents could continuously scan the existing graph to refine it. They could autonomously propose merging duplicate concepts, highlight contradicting information across documents, and suggest new relationships without explicit user prompting.

### 2. Spaced Repetition Optimization Engine
An intelligent agent could monitor the user's performance on flashcards and quizzes over time to optimize learning. Instead of simple date-based logic, an ML-driven spaced repetition engine could dynamically identify the user's weakest logical links in the graph and push micro-assessments immediately when memory retention is predicted to drop.

### 3. Multi-Agent Debates for Complex Queries
For ambiguous or highly complex questions, the system could spin up multiple specialized agents (e.g., a "Devil's Advocate" agent, a "Synthesizer" agent, and a "Domain Expert" agent). They would debate internally to synthesize the most accurate, balanced, and nuanced answer, exposing the debate summary to the user.

### 4. Autonomous Learning Path Generation
The tutor could proactively act as a curriculum designer. By analyzing the workspace's entire knowledge base and the user's concept readiness scores, the agent could generate a personalized daily or weekly syllabus, suggesting specific sections of documents to read and customized quizzes to take.

### 5. Interactive Chat Widgets & Sandboxes
Moving beyond text answers, the agent could autonomously instantiate interactive elements in the chat. If explaining a coding concept, it could spawn a live executable code sandbox. If explaining a math concept, it could spawn an interactive Desmos-style graph widget.

### 6. Cross-Workspace Synthesis
(With explicit user permission), a "Meta-Agent" could draw conceptual connections between different workspaces. If a user is learning "Linear Algebra" in one workspace and "Quantum Computing" in another, the agent could proactively explain how eigenvectors apply to quantum states.

### 7. Enduring Semantic Memory & Emotional Intelligence
The tutor could maintain a long-term profile of the user's learning style, frustrations, and preferences. If the user frequently asks for ELI5 (Explain Like I'm 5) explanations for math concepts, the agent learns this and preemptively adjusts its tone and complexity level for future math-related topics.

### 9. Markdown-Based "Skills" Architecture
Inspired by systems like nanobot and OpenClaw, the application should migrate away from hardcoded prompts in code towards a file-system-based "skills" directory. Each skill (e.g., `grade_quiz.md`, `explain_concept.md`, `debate_topic.md`) would be a standalone Markdown file that the agent can dynamically discover, read, and utilize. This allows for declarative, easily editable prompts that guide the agent's behavior without requiring code changes, unlocking true dynamic prompt discovery and open-ended tool use.

