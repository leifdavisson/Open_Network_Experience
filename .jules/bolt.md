# Bolt's Journal

Critical performance learnings and insights for Open Network Experience (ONE).

## 2026-08-30 - Aggregate Metrics Query Optimization
**Learning:** In SQLite, issuing multiple individual `SELECT COUNT(*)` queries (e.g. 8 roundtrips for alert summaries) incurs significant query execution and connection context overhead compared to a single query with conditional aggregation (`COUNT(CASE WHEN ...)`).
**Action:** Always combine multi-stat summary aggregations on the same table into a single `SELECT` statement with `COUNT(CASE WHEN ...)` or `SUM(CASE WHEN ...)` expressions.
