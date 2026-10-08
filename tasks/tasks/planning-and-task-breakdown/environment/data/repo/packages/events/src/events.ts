export type OutboxEvent =
  | { type: "search.rebuild.requested"; projectId: string; jobId: string }
  | { type: "mail.send.requested"; template: string; recipientUserId: string; dedupeKey: string };

export interface OutboxEnvelope<T extends OutboxEvent = OutboxEvent> {
  id: string;
  event: T;
  dedupeKey: string;
  createdAt: string;
}
