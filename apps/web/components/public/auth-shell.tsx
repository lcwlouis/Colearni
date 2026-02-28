import Image from "next/image";
import Link from "next/link";

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="public-entry">
      <div className="auth-shell">
        <Link href="/" className="auth-brand">
          <Image
            src="/colearniTreeLogo.png"
            alt="CoLearni"
            width={32}
            height={32}
            className="auth-brand-logo"
          />
          <span className="auth-brand-name">CoLearni</span>
        </Link>
        {children}
      </div>
    </div>
  );
}
