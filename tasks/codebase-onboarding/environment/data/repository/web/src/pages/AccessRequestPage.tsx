import { approveAccessRequest } from '../api/accessRequests';

export function AccessRequestPage({requestId}: {requestId: string}) {
  return <button onClick={() => approveAccessRequest(requestId, 'Manager approved request')}>
    Approve access
  </button>;
}
