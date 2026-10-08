import { appendOutbox } from "../../../api/src/services/outbox";

export async function claimSearchRebuilds(db: any, now: Date) {
  return db.transaction(async (tx: any) => {
    const rows = await tx.query(`
      SELECT id, project_id FROM search_rebuild_jobs
      WHERE state = 'queued' AND available_at <= $1
      ORDER BY available_at, id
      FOR UPDATE SKIP LOCKED LIMIT 25`, [now]);
    for (const row of rows) {
      const claimed = await tx.searchJobs.markRunning(row.id);
      await appendOutbox(tx, "search.rebuild.requested", { projectId: row.project_id, jobId: row.id }, `search:${row.id}`);
      if (!claimed) throw new Error("claim failed");
    }
    return rows.length;
  });
}
