# Offline connector map

This task uses frozen local exports rather than live services. The available and unavailable source states are recorded in `/root/data/source_manifest.json`:

- Email: `/root/data/emails.jsonl`
- Chat: `/root/data/chat.jsonl`
- Documents: `/root/data/documents.json`
- Calendar: `/root/data/calendar.json`
- CLM: `/root/data/contracts.json`

Do not attempt network access or request credentials. Treat the manifest's unavailable and incomplete sources as briefing limitations.
