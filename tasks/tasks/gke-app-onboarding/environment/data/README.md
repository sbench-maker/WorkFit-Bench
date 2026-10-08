# People Directory onboarding fixture

This directory is a deterministic, entirely fictional application repository snapshot for a first GKE deployment review.

- `app/` is the build context. The sample staff directory under `app/fixtures/` is for local development only and must not be included in a production image.
- `deployment-brief.json` is the platform team's frozen production contract. The named ConfigMaps and Secret already exist in the target namespace; the onboarding bundle should reference them, not recreate them.
- `traffic-profile.csv` is a 240-sample capacity snapshot supporting the resource policy recorded in the brief.

No record represents a real person, organization, cluster, or measurement.
