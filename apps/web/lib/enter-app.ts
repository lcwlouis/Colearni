import { ensureWorkspaceId } from "@/lib/workspace";

/** Minimal slice of the Next.js router we depend on. */
export type AppRouterLike = {
  push: (href: string) => void;
};

/**
 * Fake-login entry point (Phase 16.6). Reuses the existing localStorage
 * workspace flow — no real auth. Creates the workspace on first use, then
 * routes into the product dashboard. Throws if the workspace cannot be
 * ensured, so callers can keep the user on the marketing page.
 */
export async function enterApp(router: AppRouterLike): Promise<void> {
  await ensureWorkspaceId();
  router.push("/dashboard");
}
