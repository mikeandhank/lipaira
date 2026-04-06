# Foundations: Open-Source Infrastructure & Self-Hosted Tools

## What This Domain Covers

Open-source infrastructure refers to the foundational software tools that developers and organizations run to build, deploy, and operate their systems. This includes:

- **DevOps platforms**: CI/CD, source control, container orchestration
- **Data stores**: Databases, message queues, caching layers
- **Communication**: Chat, video, collaboration tools
- **Monitoring & observability**: Logging, metrics, tracing
- **Automation**: Workflow orchestration, RPA

Self-hosted tools specifically are solutions that organizations can run on their own infrastructure rather than as a managed SaaS service. The appeal: data sovereignty, cost control, customization, and avoiding vendor lock-in.

## Business Models That Actually Work

### 1. Open Core
The dominant model. Core functionality is free and open source; enterprise features (SSO, advanced security, management UIs, compliance reporting) are paid.

**Examples**: GitLab, Elastic, MongoDB, Redis, Grafana

The key insight is that "core" must be genuinely useful on its own. If you're just hiding essential features behind a paywall, the community will fork it.

### 2. Managed Services (SaaS on Top)
The open-source software runs in the cloud for you. You charge for hosting, operations, and managed infrastructure while the code remains open.

**Examples**: MongoDB Atlas, Elastic Cloud, Confluent Cloud, GitLab SaaS

This is essentially "SaaS with open source underneath." It works when operations complexity is high enough that customers will pay to avoid it.

### 3. Support + Services
The software is essentially free, but you make money from enterprise support contracts, custom development, and professional services.

**Examples**: Red Hat (historically), Canonical, many smaller infrastructure companies

This model requires deep expertise and works best when the software is mission-critical and customers have compliance requirements.

### 4. Dual Licensing
Open source under GPL (or similar), but offer a commercial license for companies that can't use GPL code (e.g., want to embed in proprietary products).

**Examples**: MySQL, Qt, MongoDB (historically)

Effective but increasingly controversial as the ecosystem moves toward more permissive licenses.

## The Self-Hosted Opportunity

Self-hosted tools occupy a specific niche:

- **Who wants them**: Enterprises with data sovereignty requirements, compliance concerns, or existing infrastructure investment; developers who want control; cost-sensitive organizations
- **The tension**: Self-hosted requires technical capacity. The more sophisticated your users, the less they'll pay for "easy." The less sophisticated, the more they need managed services
- **The moat**: Once self-hosted, switching costs are high. You're not just competing on features—you're competing on migration effort

## Market Dynamics

- **Kubernetes won container orchestration** but created a massive consulting/maintenance ecosystem
- **GitOps became mainstream** but most organizations still struggle with it
- **Observability is consolidating** around open standards (OpenTelemetry) but vendor lock-in persists
- **The "Red Hat problem"**: Build open source, get acquired, lose community momentum

## Key Technologies in This Space

| Category | Notable Open Source Projects | Commercial Players |
|----------|------------------------------|-------------------|
| Source Control | Git, Gitea | GitHub, GitLab, Bitbucket |
| CI/CD | Jenkins, ArgoCD, Tekton | GitLab CI, CircleCI |
| Containers | Docker, Podman | — |
| Orchestration | Kubernetes, Nomad | — |
| Databases | PostgreSQL, MySQL, MongoDB | PlanetScale, Neon |
| Search | Elasticsearch, Meilisearch | Algolia |
| Monitoring | Prometheus, Grafana | Datadog, New Relic |
| Chat | Matrix, Rocket.chat | Slack, Discord |
| Automation | n8n, Temporal | Zapier, Make |

The pattern: open source wins at the bottom of the stack (databases, containers, primitives) and loses at the top (workflow, collaboration, ease-of-use).
