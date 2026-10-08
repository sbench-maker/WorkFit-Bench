# Offline `gws` workspace

This fixture provides a deterministic local substitute for the Google Workspace CLI. It never contacts a network service. Commands print JSON and persist workspace state in `/root/results/workspace_state.json`.

Create a presentation (this creates one blank TITLE slide):

```bash
gws slides presentations create --json '{"title":"Example deck"}'
```

Read a presentation:

```bash
gws slides presentations get --params '{"presentationId":"prs_0043"}'
```

Populate an existing placeholder or add slides with a Slides-style batch update:

```bash
gws slides presentations batchUpdate \
  --params '{"presentationId":"prs_0043"}' \
  --json '{"requests":[
    {"insertText":{"objectId":"slide_prs_0043_1_title","text":"Deck title"}},
    {"createSlide":{"objectId":"goals","slideLayoutReference":{"predefinedLayout":"TITLE_AND_BODY"},"placeholderIdMappings":[
      {"layoutPlaceholder":{"type":"TITLE"},"objectId":"goals_title"},
      {"layoutPlaceholder":{"type":"BODY"},"objectId":"goals_body"}
    ]}},
    {"insertText":{"objectId":"goals_title","text":"Goals"}},
    {"insertText":{"objectId":"goals_body","text":"First point\nSecond point"}}
  ]}'
```

Grant a user access to the generated file ID:

```bash
gws drive permissions create \
  --params '{"fileId":"prs_0043"}' \
  --json '{"role":"writer","type":"user","emailAddress":"person@example.test"}'
```

`writer` is the Workspace API role for an editor. Run `gws --help` for the supported offline operations. Object IDs must be unique within the presentation.
