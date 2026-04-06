# Machine Learning — Contrarian Views

## What Most People Get Wrong

### 1. "ML will solve any problem with enough data"

**Wrong:** Feed data in, get insights out. More data = better results.

**Reality:**
- 85% of ML projects fail
- Data must be clean, representative, and ML-ready
- Garbage in, garbage out amplified — flawed data → flawed models
- Most companies underestimate data preparation time

### 2. "Data scientists are the bottleneck"

**Wrong:** Hire more data scientists to speed up ML projects.

**Reality:**
- Problem is usually misalignment between business and ML
- Teams lack shared definitions of success
- More scientists without clear problems = more wasted work

### 3. "ML is a technology problem"

**Wrong:** ML is a technical challenge to be solved by engineers.

**Reality:**
- ML is a business transformation
- Success requires organizational change
- Integration with existing systems is the hard part

### 4. "The model is the product"

**Wrong:** Building the model is the hard part. Deployment is easy.

**Reality:**
- Netflix never deployed its $1M prize-winning algorithm due to complexity
- Deployment requires infrastructure, monitoring, integration
- Models degrade in production (data drift)

### 5. "ML can be done on the cheap"

**Wrong:** AI is low-resource. Throw some data at it.

**Reality:**
- Requires significant time and financial investment
- Data acquisition, cleaning, labeling cost real money
- Compute costs add up quickly

### 6. "Accuracy is the only metric that matters"

**Wrong:** If accuracy is high, the model is good.

**Reality:**
- Context matters: false positives vs. false negatives
- In fraud detection, false positives annoy customers
- In medical diagnosis, false negatives are dangerous
- Business metrics > academic metrics

### 7. "Deep learning is always better"

**Wrong:** Neural networks outperform all other algorithms.

**Reality:**
- Traditional ML often outperforms deep learning on structured data
- Deep learning requires more data and compute
- Interpretability matters for business decisions
- Simple models are often "good enough"

### 8. "ML will replace humans"

**Wrong:** AI will automate away human workers.

**Reality:**
- ML augments human decision-making
- Human judgment still needed for edge cases
- Best results are human-AI collaboration
- New roles created (ML ops, data engineering)

### 9. "Real-time is always better"

**Wrong:** Batch processing is outdated. Real-time is superior.

**Reality:**
- Not all problems need real-time
- Batch is simpler, cheaper, often sufficient
- Real-time introduces complexity and cost
- "Good enough" latency often works

### 10. "It's a solved problem"

**Wrong:** ML is mature. Just use pre-built solutions.

**Reality:**
- 85% failure rate suggests otherwise
- Each business problem is unique
- Pre-built models may not fit your data
- Maintenance is ongoing, not one-time

---

## Where Conventional Wisdom Fails

| Conventional Wisdom | Why It Fails |
|---------------------|--------------|
| More data = better | Data quality, representativeness matter |
| Hire more scientists | Problem is alignment, not headcount |
| Model is the product | Deployment, integration are harder |
| ML is cheap | Significant time and money required |
| Accuracy = success | Business context, false positives/negatives |
| Deep learning wins | Traditional ML often better for structured data |
| ML replaces humans | Augmentation > automation |
| Real-time required | Batch is often sufficient |

---

## What Separates Success from Failure

1. **Clear business problem** — Defined before touching data
2. **Realistic expectations** — "Good enough" > "perfect"
3. **Data readiness** — Clean, representative, ML-ready
4. **Cross-functional teams** — Business + Engineering + Data
5. **Iterative approach** — MVP → iterate → scale
6. **Production monitoring** — Track drift, retrain as needed
7. **Integration focus** — Build for production from day one
