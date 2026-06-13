# PR Pilot — Devpost Submission Narrative (955 words)

**How does your team use AI?**

PR Pilot doesn't just use AI — it is AI. Our five-agent pipeline (Reviewer → Fixer → Tester → Verifier → Escalator) operates the entire code review business autonomously. There are no human code reviewers. There are no humans deciding which PRs to approve. The agents make these decisions independently, in production, every day.

The AI agents are deployed on Google Cloud Run as a continuously running service that listens for GitHub webhooks. When a pull request opens, the chain fires automatically. Agent 1 (Reviewer) analyzes diffs using Gemini API for bugs, security vulnerabilities, and performance regressions. Agent 2 (Fixer) generates code patches. Agent 3 (Tester) detects the project's test framework and writes unit tests. Agent 4 (Verifier) confirms no regressions. Agent 5 (Escalator) makes the final decision — auto-approve, request changes, or escalate to a human.

We dogfood PR Pilot on its own repository. Every pull request to the PR Pilot codebase is reviewed by the agents. The agents have caught real bugs in our own code, generated patches, and autonomously approved safe changes. We do not manually review PRs — we trust the agents, and we have the execution logs to prove they're doing the job.

Gemini API is our sole LLM provider, used for all five agents. We use Gemini's structured output (response schemas) extensively — each agent outputs typed JSON that flows into the next agent in the chain. This isn't a chatbot bolted onto a CRUD app. The business cannot function without the agents.

**What does a human do?**

Humans write the code. The agents review it.

Our split is clear: developers open pull requests, and the AI handles everything that happens after. For standard changes (bug fixes, feature additions, dependency updates), the agents handle 100% of the review process — from analysis to approval. Humans only see the review summary posted on their PR.

The Escalator agent classifies each review into one of three categories: auto-approve (low risk, all checks pass), request changes (issues found, fixes attached), or escalate to human (critical security bugs, complex architectural decisions, ambiguous changes). In practice, more than 90% of reviews are resolved without human intervention.

Our role as the "team" is to build and maintain the infrastructure that lets the agents operate. We write the agent prompts, configure the deployment pipeline, monitor the dashboards, and handle the rare escalations. But the business itself — reviewing code, generating fixes, making merge decisions — runs on AI.

This is what "AI-native operations" means to us: the agents are the operations. Without them, there is no service. Without them, we would need to hire a team of code reviewers. Instead, we built a system where five AI agents do that work, at a price point that makes enterprise-grade code review accessible to any dev team.

**What jobs and economic opportunities does this create?**

PR Pilot targets the 2-10 person dev team that can't afford dedicated code review. These teams — bootstrapped startups, indie developers, small agencies — ship with bugs because they can't justify the cost of a full-time reviewer. Some skip review entirely.

For $99/month, these teams get the same rigor as a FAANG code review process. This enables three things:

First, higher quality software from small teams. Bugs that would have reached production get caught by the Reviewer agent. SQL injection, XSS, hardcoded credentials — the agents find these before they ship.

Second, faster shipping. Small teams no longer have to choose between "review properly" and "ship quickly." The agents review every PR in ~90 seconds, so there's no bottleneck.

Third, economic enablement. A solo developer building a SaaS product can now compete on code quality with funded startups. The playing field tilts slightly toward the underdog.

The service itself creates economic opportunity. We're building PR Pilot as a sustainable SaaS business. At $99/mo per team, with 30 customers, we generate $2,970 MRR from a single-person operation. This is a new kind of business — one where AI agents do the revenue-generating work.

**What's the story of building this business?**

We started three weeks ago with a question: what if code review didn't need humans?

The first version was a single Gemini API call that analyzed a PR diff and posted a comment. It worked, but it was shallow — like a linter with a chatbot interface. The breakthrough came when we realized the review pipeline could be decomposed into specialized agents, each responsible for one stage of the quality lifecycle.

We built five agents. Each has a distinct system prompt, a specific output schema, and a defined handoff to the next agent. The orchestration engine runs them sequentially, passing structured context from one to the next. State is persisted to disk for auditability — every decision, every finding, every patch is logged with timestamp and reasoning.

The hardest technical challenge was reliability. Gemini API calls can fail, time out, or return unexpected output. We added exponential retry with jitter, structured output enforcement via response schemas, and chain short-circuiting — if any agent fails, the pipeline aborts cleanly rather than posting a misleading half-review.

The business challenges were harder. We had to set up Stripe for real payment processing, build a landing page that actually converts, and figure out how to reach small dev teams. We launched on GitHub with a live emulator that shows the agent pipeline in action — you can watch it process common vulnerabilities without installing anything.

We're three weeks into a 90-day sprint. The service is live, reviewing real PRs, with real Stripe payment links. Our goal is 30 paying customers by the August deadline. We're documenting everything — agent execution logs, revenue dashboards, customer feedback — because the story of building an AI-native business from zero is as important as the product itself.

PR Pilot demonstrates that a single developer, with AI agents as the operations team, can build and run a revenue-generating SaaS business. That's the promise of this XPRIZE — and we're proving it works.
