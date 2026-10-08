export interface ProjectNotificationPreferences {
  mentionEmail: boolean;
  version: number;
}

export async function getProjectNotificationPreferences(projectId: string): Promise<ProjectNotificationPreferences> {
  return window.api.get(`/api/projects/${projectId}/notification-preferences`);
}

export async function updateProjectNotificationPreferences(projectId: string, input: ProjectNotificationPreferences) {
  return window.api.put(`/api/projects/${projectId}/notification-preferences`, input);
}
