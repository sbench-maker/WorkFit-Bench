export type ProjectRole = "viewer" | "member" | "admin" | "owner";
export type MembershipStatus = "pending" | "active" | "suspended";

const rank: Record<ProjectRole, number> = { viewer: 0, member: 1, admin: 2, owner: 3 };

export function hasProjectRole(actual: ProjectRole, minimum: ProjectRole): boolean {
  return rank[actual] >= rank[minimum];
}
