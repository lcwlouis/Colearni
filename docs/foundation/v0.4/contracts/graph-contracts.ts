/** Desk v0.4 graph design vocabulary. Not a migration or runtime validator. */
export type ConceptLevel = "umbrella" | "topic" | "subtopic" | "granular";
export type ConceptKind = "concept" | "skill" | "misconception" | "example";
export type RelationType = "prerequisite" | "contains" | "application" | "related";
export type RelationReview = "proposed" | "confirmed" | "rejected";
export interface GraphEvidenceRef {
  objectId: string;
  revision: number;
  locator: string;
}
export interface ConceptRecord {
  id: string;
  workspaceId: string;
  scopeId: string;
  title: string;
  slug: string;
  conceptLevel: ConceptLevel;
  nodeKind: ConceptKind;
  revision: number;
}
export interface ConceptRelation {
  id: string;
  workspaceId: string;
  scopeId: string;
  sourceId: string;
  targetId: string;
  relationType: RelationType;
  relationSchemaVersion: "desk-relations/1-draft";
  review: RelationReview;
  evidenceRefs: GraphEvidenceRef[];
  /** Authoritative actor identity must be supplied by the trusted service. */
  suggestedBy: "learner" | "tutor" | "import" | "curator";
  revision: number;
}
/** Mastery and read permissions deliberately do not live on a relation. */
export interface ConceptDocumentReference {
  conceptId: string;
  documentId: string;
  documentRevision: number;
  locator?: string;
  relation: "explains" | "questions" | "practises" | "mentions";
  review: RelationReview;
}
