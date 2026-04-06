# Open Questions: Known Unknowns in Open-Source Infrastructure

These are questions where I lack confident answers despite research. They're "known unknowns" that would require deeper investigation or market data to resolve.

---

## Question 1: Is the "Open Source Sustainability Crisis" Real or Just a Narrative?

**The question**: Is open source infrastructure actually facing a funding/sustainability crisis, or is this a narrative pushed by companies that want to sell commercial licenses?

**What I don't know**:
- How much "open source" infrastructure is actually maintained by well-funded teams vs. one-person shows held together with metaphorical duct tape
- Whether the crisis is concentrated in specific categories (e.g., low-level infrastructure) vs. everywhere
- If demand for open source maintainers actually exceeds supply, or if this is a coordination problem
- Whether organizations that depend on open source are actually increasing their contributions, or just talking about it

**My uncertainty**: The narrative is compelling (and pushed hard by companies like GitLab, MongoDB, Elastic who benefit from it). But I'm not sure I can validate whether it's actually gotten worse or if it's been this way forever and we're just paying more attention.

---

## Question 2: Will Kubernetes Consolidation Kill or Strengthen Open-Source Infrastructure?

**The question**: As Kubernetes matures and becomes "boring infrastructure," are we seeing the end of open-source infrastructure startups? Or does consolidation create new opportunities?

**What I don't know**:
- Whether the "Kubernetes plateau" means less opportunity or just shifts the bottleneck (from "how do we orchestrate" to "how do we secure/observe/manage")
- If venture funding for infrastructure startups has actually decreased, or if it's just moved to adjacent areas (platform engineering, developer experience)
- Whether the "platform engineering" movement is a real trend or a rebranding of DevOps

**My uncertainty**: Infrastructure seems to go through cycles—build, standardize, commoditize, then build on top. But I can't confidently predict whether we're at the end of the cycle or in a quiet period before the next wave.

---

## Question 3: Can Any Open-Source Project Successfully Compete With Hyperscalers?

**The question**: AWS, GCP, and Azure can clone any open-source product and offer it as a managed service at scale. Can any open-source company genuinely compete long-term, or is the best outcome acquisition by a cloud provider?

**What I don't know**:
- Whether the "cloning" problem is getting worse (more services) or better (customers are waking up to vendor lock-in)
- If there are defensible moats beyond "developer experience" that don't involve being acquired
- What the long-term trajectory is for companies like Elastic (who fought AWS) vs. Confluent (who partnered with AWS)
- Whether the answer is different for "infrastructure" (databases, queues) vs. "application layer" (monitoring, CI/CD)

**My uncertainty**: The pattern so far is mixed—some companies fight and survive (MongoDB), some fight and struggle (Elastic), some partner and grow (Confluent). I don't have a confident model for predicting which strategy works in which situation.

---

## Why These Questions Matter

These aren't academic. They directly inform:
- Where to invest (or advise others to invest)
- Which business models are viable
- Whether to build on open source or buy
- What career bets to make

If you have strong opinions on any of these, I'd genuinely want to hear them—these are the gaps in my mental model.
