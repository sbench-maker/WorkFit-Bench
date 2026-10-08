export async function approveAccessRequest(requestId: string, reason: string) {
  const response = await fetch(`/api/v1/access-requests/${requestId}/approve`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({reason}),
  });
  if (!response.ok) throw new Error('approval failed');
  return response.json();
}
