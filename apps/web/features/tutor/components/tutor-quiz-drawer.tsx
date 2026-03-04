import { LevelUpCard } from "@/components/level-up-card";
import type { LevelUpState } from "@/lib/tutor/level-up-state";

interface TutorQuizDrawerProps {
  closingDrawer: "graph" | "quiz" | null;
  levelUpState: LevelUpState;
  onStartQuiz: () => void;
  onAnswerChange: (itemId: number, value: string) => void;
  onSubmitQuiz: () => void;
  dispatchReset: () => void;
}

export function TutorQuizDrawer({
  closingDrawer,
  levelUpState,
  onStartQuiz,
  onAnswerChange,
  onSubmitQuiz,
  dispatchReset,
}: TutorQuizDrawerProps) {
  return (
    <aside className={`panel quiz-drawer${closingDrawer === "quiz" ? " closing" : ""}`}>
      <LevelUpCard
        state={levelUpState}
        onStartQuiz={onStartQuiz}
        onAnswerChange={onAnswerChange}
        onSubmitQuiz={onSubmitQuiz}
        onRetryCreate={onStartQuiz}
        onRetrySubmit={onSubmitQuiz}
        onStartNew={() => {
          dispatchReset();
          // Auto-start new quiz after reset
          setTimeout(() => onStartQuiz(), 0);
        }}
      />
    </aside>
  );
}
