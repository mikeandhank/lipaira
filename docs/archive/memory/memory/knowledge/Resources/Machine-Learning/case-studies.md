# Machine Learning - Case Studies

## Real-World ML Successes

### 1. Netflix Recommendation System
- **What**: Personalized movie/show recommendations
- **ML Approach**: Collaborative filtering + content-based filtering + deep learning
- **Result**: 75% of viewer activity driven by recommendations
- **Key Insight**: Ensemble methods beat single models

### 2. Netflix's Content Demand Prediction
- **What**: Predicting what content to create
- **ML Approach**: Time-series forecasting + NLP on social signals
- **Result**: Data-driven content investment decisions
- **Key Insight**: ML can predict cultural trends, not just user behavior

### 3. Amazon's Logistics Optimization
- **What**: Inventory placement, delivery routing
- **ML Approach**: Reinforcement learning + predictive analytics
- **Result**: Reduced delivery times and costs
- **Key Insight**: ML excels at optimization under constraints

### 4. Google Translate
- **What**: Neural machine translation
- **ML Approach**: Sequence-to-sequence neural networks + attention
- **Result**: Quality leap from rule-based to neural
- **Key Insight**: Scale + data > clever algorithms

### 5. Medical Imaging Diagnostics
- **What**: Detecting diseases from X-rays, CT scans
- **ML Approach**: Convolutional neural networks (CNNs)
- **Result**: Matched or exceeded radiologist accuracy
- **Key Insight**: High-stakes applications require human-in-loop

### 6. AlphaFold (DeepMind)
- **What**: Protein structure prediction
- **ML Approach**: Transformer-based deep learning
- **Result**: Solved 50-year biology challenge
- **Key Insight**: Domain-specific architectures matter

---

## Failures and Lessons

### 1. IBM Watson for Oncology
- **What**: AI diagnosis for cancer treatment
- **Why It Failed**: Trained on synthetic data, didn't generalize to real patients
- **Lesson**: Real-world data > synthetic data

### 2. Google Flu Trends
- **What**: Predicting flu outbreaks from search queries
- **Why It Failed**: Overfitting to specific patterns, didn't adapt to changing behavior
- **Lesson**: Retrain frequently, don't trust correlations forever

### 3. Amazon Hiring Algorithm
- **What**: Resume screening AI
- **Why It Failed**: Biased against women (trained on historical hiring data)
- **Lesson**: Audit for bias, clean training data matters

---

## Key Takeaways for Our Business

1. **Start simple** - Rule-based + basic ML > complex deep learning initially
2. **Data quality** - Garbage in, garbage out
3. **Human oversight** - Always have humans in the loop for high-stakes decisions
4. **Iterate fast** - Ship, measure, improve
5. **Domain expertise** - Combine ML with domain knowledge