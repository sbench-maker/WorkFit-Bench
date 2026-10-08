export const retryPolicy = { attempts: 5, backoffSeconds: [30, 120, 600, 1800, 7200] } as const;

export async function consumeMailRequested(db: any, envelope: any) {
  if (await db.delivery.existsByDedupeKey(envelope.dedupeKey)) return { duplicate: true };
  const rendered = await db.templates.render(envelope.event.template, envelope.event.context);
  await db.mail.send(envelope.event.recipientUserId, rendered);
  await db.delivery.record({ dedupeKey: envelope.dedupeKey, state: "sent" });
  return { duplicate: false };
}
