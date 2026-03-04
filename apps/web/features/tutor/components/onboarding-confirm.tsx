"use client";

type Props = {
  conceptName: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function OnboardingConfirm({ conceptName, onConfirm, onCancel }: Props) {
  return (
    <div className="onboarding-confirm">
      <p className="onboarding-confirm__prompt">
        Ready to learn about <strong>{conceptName}</strong>?
      </p>
      <div className="onboarding-confirm__actions">
        <button type="button" className="onboarding-confirm__btn onboarding-confirm__btn--primary" onClick={onConfirm}>
          Start learning
        </button>
        <button type="button" className="onboarding-confirm__btn onboarding-confirm__btn--secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
