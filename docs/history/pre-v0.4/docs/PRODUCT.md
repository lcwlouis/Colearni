# Product brief

## Purpose

Desk is a calm learning workspace where a person works through difficult ideas with a tutor. It should help the learner become able to explain, use, question, or extend an idea—not simply obtain a polished answer.

The founder described three problems: difficulty maintaining attention within overwhelming learning activities; effortless answers that create a misleading sense of understanding; and not knowing where to begin with a broad topic. These are problem hypotheses informed by the founder's experience, not validated claims about every learner.

## Experience principles

- Help is available without being earned. Teach beginners; do not repeatedly interrogate someone who lacks the prerequisites.
- Explain one coherent difficulty at a time. Avoid both long default essays and constant mandatory “continue” clicks.
- Ask for meaningful participation when useful: a prediction, comparison, revision, application, or explanation. Not every turn needs a question.
- Adapt to the task, prior understanding, preferences, and accessibility needs. Do not assign a permanent “learning style” identity.
- Keep the learner in control. Help, pause, skip, direct explanation, and changing the goal are legitimate choices.
- Independent performance is different from assisted work. Unknown understanding is not failure.
- Make stopping and returning normal. A session can be useful without an assessment.
- Use graphs to orient learning and make connections, not to gate access to explanations.

## Entry and destination

Support both a broad intention and supplied material: a paper, article, problem, or code. The first proposed demonstration is a source-anchored paper-learning session; broad-goal entry should lead into the same goal and activity model rather than another application.

Ask “What would you like to be able to do with this?” Offer source-specific suggestions such as explaining the argument, using the method, or evaluating the evidence. Allow a custom goal and “help me decide.” Bloom categories may inform internal planning and assessment, but do not require the learner to select taxonomy terminology or imply one linear ranking captures every goal.

## Core journey

Bring material or an intention → choose a useful destination → establish a tentative starting point → work through one activity → receive situated help → revise or apply → leave a clear return point.

An initial probe is optional and brief. Initial beliefs about the learner remain uncertain; refine them from actual work. The source stays reachable. Teach just enough prerequisite material for the chosen goal, with deeper branches available rather than mandatory.

## Desk model

A persistent work surface contains addressable cards and learner work. The tutor can refer to an equation, table cell, paragraph, code revision, or plotted object. A map supports the journey but is not the mandatory home surface. Card bodies vary; their ownership, provenance, placement, history, and assistance controls remain consistent.

A specialist means appropriate strategies, tools, and assessment criteria—not necessarily an independent autonomous agent or a named persona. A mathematics activity, evidence critique, and coding exercise should not be forced through identical teaching sequences.

## First prototype scenario

Use the clearly labelled synthetic fixture, not an actual uploaded paper. A learner wants to explain a method in a demonstration article. They inspect an excerpt, receive a short worked example, write a note, adjust a reviewed scalar simulation, and return to their own explanation. A scripted tutor action adds supporting material without disturbing typing. Undo removes that addition but preserves later learner work.

The prototype must make simulation versus reality explicit: no functioning file ingestion, model tutoring, secure multi-user storage, or learner assessment is implied by scripted UI states.

## Phased scope

**Frontend prototype:** fixture-based desk, shared card envelope, learner notes, tutor contributions, source references, semantic highlighting, two bundled example plugins, deterministic proposed-change/history states, and a return-session story.

**First real vertical slice, after review:** source ingestion and anchoring, authenticated persistence, scoped tutoring, enforceable ownership and permission checks, bounded context, and modest evidence tracking.

**Later:** private generated engines in an isolated runtime; reviewed plugin releases; Discover; cross-desk discovery and more complex simulations. Default plugins already use the common contract so this later work need not replace the UI foundation.

Do not build marketplace, arbitrary execution, autonomous agent teams, payment flows, multiplayer, or a giant workspace graph during the first frontend handoff.

## Evidence of usefulness

Observe whether people find a next action, obtain useful help, stay involved, recognise who authored content, and resume without losing work. Later evaluate independent explanations/applications and delayed retention with reviewed assessment criteria. Message volume, time spent, and generated-card counts are not primary learning outcomes. Storybook tests establish UI behaviour, not learning efficacy.
