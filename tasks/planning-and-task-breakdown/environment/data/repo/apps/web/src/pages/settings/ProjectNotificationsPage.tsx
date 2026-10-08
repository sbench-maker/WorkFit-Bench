import { SettingsPanel } from "../../components/SettingsPanel";
import { useProjectPermission } from "../../permissions/useProjectPermission";

export function ProjectNotificationsPage({ projectId }: { projectId: string }) {
  const canEdit = useProjectPermission(projectId, "member");
  return (
    <SettingsPanel title="Notifications" description="Choose how this project contacts you.">
      <label><input type="checkbox" disabled={!canEdit} /> Email me when I am mentioned</label>
    </SettingsPanel>
  );
}
