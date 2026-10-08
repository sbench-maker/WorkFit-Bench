# AURORA-2 planning snapshot field guide

All records are fictional planning inputs. Treat `selection_status=selected` as the current operating footprint. For gate scoring, `sites` is the number of selected rows and `eligible_population` is the sum of their `eligible_pool` values. The bottom-up CRM enrollment forecast is the sum, over selected sites, of `expected_enrollments_per_active_month * max(enrollment_months - startup_months, 0)`; keep the decimal estimate rather than rounding each site first. Missing readiness fields occur only in non-selected pipeline records and must not be imputed into the selected footprint.

Endpoint dimension scores use a 0-100 planning scale. The study is a drug profile. The response-rate assumptions are an internal anchor for first-pass estimation only and require the named biostatistician's confirmation before a protocol is finalized.
