import { z } from "zod";
import { hasProjectRole } from "@orbitdesk/permissions/project-role";

const updatePreference = z.object({ mentionEmail: z.boolean(), version: z.number().int().nonnegative() });

export async function getProjectNotificationPreferences(ctx: any) {
  const membership = await ctx.memberships.requireActive(ctx.user.id, ctx.params.projectId);
  return ctx.preferences.find(ctx.params.projectId, membership.userId);
}

export async function putProjectNotificationPreferences(ctx: any) {
  const membership = await ctx.memberships.requireActive(ctx.user.id, ctx.params.projectId);
  if (!hasProjectRole(membership.role, "member")) return ctx.reply.forbidden();
  const input = updatePreference.parse(ctx.body);
  const updated = await ctx.preferences.updateVersioned(ctx.params.projectId, ctx.user.id, input);
  if (!updated) return ctx.reply.conflict({ code: "STALE_VERSION" });
  await ctx.audit.append({
    type: "project_notification.updated",
    actorId: ctx.user.id,
    projectId: ctx.params.projectId,
    changedFields: ["mentionEmail"],
  });
  return updated;
}
