import type { Metadata } from "next";

import { MarketingHomeContent } from "@/components/marketing/MarketingHomeContent";

export const metadata: Metadata = {
  title: "Colearni — Learn anything as a graph, with a Socratic tutor",
  description:
    "Colearni turns a goal into a concept graph, then coaches you through it one concept at a time with a Socratic tutor and real mastery.",
};

export default function MarketingHomePage() {
  return <MarketingHomeContent />;
}
