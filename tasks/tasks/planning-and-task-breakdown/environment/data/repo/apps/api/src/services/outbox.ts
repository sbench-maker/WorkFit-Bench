export async function appendOutbox(tx: any, type: string, payload: unknown, dedupeKey: string) {
  return tx.outbox.insert({ type, payload, dedupeKey, attempts: 0, availableAt: new Date() });
}
