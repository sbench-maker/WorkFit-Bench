export const featureFlags = {
  newProjectSearch: { default: true },
  scheduledProjectDigest: { key: "scheduled_project_digest", default: false },
} as const;

export type FeatureFlagKey = typeof featureFlags[keyof typeof featureFlags]["key"];
