# Architecture

## Runtime

```text
Browser
  |
  v
Next.js web
  |
  | REST + cookie/bearer session
  v
FastAPI
  |\
  | \
  v  v
PostgreSQL  JudgeGuard Engine
               |
               +-- assignment optimizer
               +-- normalization
               +-- calibration/drift
               +-- ranking/stability
               +-- influence/flip-set
               +-- rubric sensitivity
               +-- adaptive review
```

## Security boundary

Authentication and authorization live in FastAPI dependencies. A judge is authorized only against assignments belonging to that judge. The frontend is never the security boundary.

Raw evaluations are append-only from the analytics perspective. Analytics produce separate run records.

## Innovation flow

```text
Judge profiles + projects + constraints
              |
              v
      assignment optimizer
              |
              v
     counterbalanced queues
              |
              v
          evaluations
              |
              v
 normalization + calibration
              |
              v
         ranking engine
          /      |      \
         v       v       v
    stability influence sensitivity
         \       |       /
          \      |      /
            v    v    v
          integrity state
                |
        +-------+--------+
        |                |
      robust           fragile
        |                |
    publish        adaptive review
                         |
                   new evaluation
                         |
                    recalculate
```

## Offline requirement

No hosted database, hosted authentication or external API is required. Docker Compose is the runtime boundary.
