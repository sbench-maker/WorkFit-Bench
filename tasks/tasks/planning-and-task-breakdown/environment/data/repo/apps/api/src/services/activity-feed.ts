import type { ActivityRow } from "@orbitdesk/db/schema";

export async function listProjectActivity(
  db: any,
  projectId: string,
  from: Date,
  to: Date,
  limit = 50,
): Promise<ActivityRow[]> {
  return db.activity.findMany({
    where: { projectId, occurredAt: { gte: from, lt: to } },
    orderBy: [{ occurredAt: "desc" }, { activityId: "desc" }],
    limit,
  });
}
