const forbiddenPayloadKey = /email|token|body/i;

export async function appendAudit(db: any, event: { type: string; actorId: string; projectId: string; changedFields: string[] }) {
  for (const key of Object.keys(event)) {
    if (forbiddenPayloadKey.test(key)) throw new Error(`sensitive audit key: ${key}`);
  }
  return db.audit.insert(event);
}
