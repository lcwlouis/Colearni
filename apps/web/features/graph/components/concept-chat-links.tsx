"use client";

import { useRouter } from "next/navigation";

type Props = {
  conceptName: string;
  conceptId: number;
};

export function ConceptChatLinks({ conceptName, conceptId }: Props) {
  const router = useRouter();

  const handleStartChat = () => {
    const encodedTopic = encodeURIComponent(conceptName);
    router.push(`/tutor?topic=${encodedTopic}`);
  };

  return (
    <div className="concept-chat-links">
      <button
        type="button"
        className="concept-chat-links__start"
        onClick={handleStartChat}
      >
        💬 Start a new chat about {conceptName}
      </button>
    </div>
  );
}
