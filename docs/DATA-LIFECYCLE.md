# Data Lifecycle

```
Upload
  ↓
Validate
  ↓
Profile
  ↓
Quality analysis
  ↓
AI recommendation
  ↓
Human review
  ↓
Approve
  ↓
Deterministic transform
  ↓
New version
  ↓
Re-profile
  ↓
Report + Export
```

## Integrity rules

1. Uploaded raw data is immutable.
2. AI produces plans, not direct mutations.
3. Transformations execute only after approval.
4. Every refinement produces a new version.
5. Quality is measured again after refinement.
6. Exported artifacts are tied to an authenticated dataset/version context.
