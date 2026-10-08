# Edge delivery network module

This fictional module models the topology policy for an edge-routing service without contacting a cloud API. It uses Terraform's built-in `terraform_data` resource, so initialization and tests are credential-free and offline.

The contract is intentionally small but operationally important:

- Development defaults to two private subnets and no private endpoint attachments.
- Subnets use sequential `/24` networks beginning at child number 10 and rotate through the supplied availability zones.
- Enabling private endpoints attaches one endpoint to every private subnet; disabling the flag attaches none.
- Caller tags are preserved, except `Environment`, `ManagedBy`, and `Service` are controlled by the module.
- `environment` accepts `dev`, `staging`, or `prod`; `subnet_count` accepts whole numbers from 2 through 6.
- Production plans need at least three subnets, even though development defaults to two.

The pull-request suite is expected to use `terraform test` in plan mode. No apply-mode scenario is needed for this module.
