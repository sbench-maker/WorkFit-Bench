export interface ProjectNotificationPreferenceRow {
  projectId: string;
  userId: string;
  mentionEmail: boolean;
  version: number;
  updatedAt: Date;
}

export interface MembershipRow {
  projectId: string;
  userId: string;
  role: "viewer" | "member" | "admin" | "owner";
  status: "pending" | "active" | "suspended";
}

export interface UserRow {
  id: string;
  emailOptOut: boolean;
}

export interface ActivityRow {
  activityId: string;
  projectId: string;
  kind: "task_created" | "task_completed" | "comment_added" | "membership_changed";
  occurredAt: Date;
  summary: string;
}

export interface OutboxRow {
  id: string;
  type: string;
  payload: unknown;
  dedupeKey: string;
  attempts: number;
  availableAt: Date;
}
