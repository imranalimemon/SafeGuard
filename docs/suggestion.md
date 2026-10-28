# Remaining work and recommendations

The current application has authentication, encrypted camera secrets, real live/upload analysis, review/archive workflows, filtered CSV/PDF, saved settings, observation-based analytics, preview/live alert gates and operational logs. See [phase reports](progress/phase1.md) and [final QA](qa-report.md) for observed evidence.

Priority remaining work is evidence quality and deployment validation:

1. Create a leakage-free split and retrain once authorized. Preserve originals and document exact model/export provenance. Evaluate with an explicitly agreed low-score policy for full AP, plus the retained deployment threshold.
2. Manually label a balanced worker subset for PPE relationships and face visibility. Current box-derived compliance proxies cannot validate complete three-item compliance or missing-mask recall.
3. Test physical camera reconnect/shutdown, actual deployment CPU/GPU capacity, HTTPS/secret management and real SMTP/Twilio with deliberate recipient consent. Preview QA does not prove remote delivery.
4. If needed, add identity tracking, capture sharing across viewers, retention/backup policy and multi-user roles. They are not current features or validated capacity claims.
5. Consider bundle/code splitting after deployment needs are known. Keep current metrics linked to their producing commands and preserve all limitations in the defense/report.

Do not present unknown mask visibility as compliance, sampled observations as unique workers, or leaked-split AP as final generalization performance.
