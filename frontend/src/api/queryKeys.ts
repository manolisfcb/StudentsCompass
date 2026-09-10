/**
 * Query keys live in one place so an invalidation cannot miss a cache entry
 * because two features spelled the same resource differently (plan 08 §7).
 * Features append their own namespaces as they are migrated.
 */
export const queryKeys = {
  session: {
    /** Read by every shell and guard, so it has exactly one key. */
    current: ["session"] as const,
  },
  smoke: {
    origin: ["smoke", "origin"] as const,
  },
  profile: {
    current: ["profile"] as const,
  },
  resumes: {
    list: ["resumes"] as const,
    courseAuditAttempts: ["resumes", "course-audit-attempts"] as const,
  },
  questionnaire: {
    current: ["questionnaire"] as const,
    profile: ["questionnaire", "profile"] as const,
  },
  dashboard: {
    student: ["dashboard", "student"] as const,
  },
  resources: {
    list: ["resources"] as const,
    detail: (resourceId: string) => ["resources", resourceId] as const,
    progress: (resourceId: string) => ["resources", resourceId, "progress"] as const,
  },
  roadmaps: {
    list: ["roadmaps"] as const,
    saved: ["roadmaps", "saved"] as const,
    detail: (slug: string) => ["roadmaps", slug] as const,
  },
  careerLab: {
    targetRoles: ["career-lab", "target-roles"] as const,
    skillReview: (resumeId: string) => ["career-lab", "skill-review", resumeId] as const,
    routeRuns: ["career-lab", "route-runs"] as const,
  },
} as const;
