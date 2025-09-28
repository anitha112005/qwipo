# Qwipo: Personalized B2B Product Recommendation System

## Hackathon Team Project

---

### 📎 Deliverables

- **PPT Presentation:**  
https://docs.google.com/presentation/d/1940sBaxmykr73T6FfZ_jj6R1wSBkLlCo/edit?usp=drive_link&ouid=112860704495655260383&rtpof=true&sd=true)]

- **Project Video:**  
  https://drive.google.com/file/d/1ZO3NEpkGfvnq75JZrC66pRz0l82CquhN/view?usp=drive_link

---

## Team Members

<!-- Add your team members and roles here -->
- Ujwal kriti - Team Lead
- Simoni - Team Member
- Vardhan - Team member
- Anitha - Team Member
- Srithika - Team Member

---

## Overview

Qwipo bridges the gap for traditional vendors, manufacturers, and suppliers by providing digital tools, logistics, and financing for B2B retail.  
Our hackathon project is an AI-powered personalized recommendation system to revolutionize retailer experience and optimize distributor business outcomes.

---

## Problem Statement

Retailers on Qwipo’s marketplace face:
- Repetitive buying behaviour and missed relevant products
- Suboptimal business outcomes for both retailers and distributors

**Goal:**  
Deliver a recommendation engine that boosts cross-selling, increases basket value, improves inventory turnover, and helps retailers discover new, profitable products.

---

## Solution Architecture

### Hybrid Recommendation Engine

- **Collaborative Filtering:**  
  Learns from retailer purchase history (what similar stores bought).
- **Content-Based Filtering:**  
  Suggests products similar to those previously bought, using product attributes.
- **Deep Learning Sequence Modeling:**  
  Predicts next likely purchases using retailer buying patterns.

### Business Optimization Layer

- Filters recommendations by stock quantity, profit margin, and sales velocity to ensure actionable, profitable results.

---

## Tech Stack

- **Web & Microservices:** Node.js (Fastify), Python (FastAPI), PostgreSQL, MongoDB
- **ML Frameworks:** scikit-learn, TensorFlow / PyTorch
- **APIs:** REST/GraphQL, WebSocket
- **Advanced Integration:** OpenAI/Gemini for NLP and vector embeddings

---

## Features

- Retailer profiling (store type, location, credit tier)
- Seasonal and temporal feature engineering
- Product attributes: margin, expiry, supplier region
- Real-time recommendations (WebSocket integration)
- Business-aware ranking

---

## Team Workflow

1. **Data Acquisition:**  
   - Use public datasets (Kaggle/UCI) or generate synthetic B2B data
   - Engineer rich features: retailer type, order frequency, product margins

2. **Model Development:**  
   - Encode IDs, design two-tower DNN (collaborative + content-based)
   - Integrate product metadata and business metrics
   - Train on temporally split data

3. **Business Ranking:**  
   - Merge model relevance with business metrics
   - Apply weighted scoring: prioritize profitable, high-stock, fast-moving products

4. **Deployment:**  
   - Serve via FastAPI microservices
   - Orchestrate business logic and real-time API responses with Node.js
   - Containerize for hackathon demo (Docker)

---

## Business Impact

| Challenge                 | Solution Outcome                                   |
|---------------------------|---------------------------------------------------|
| Repetitive buying         | ↑ Cross-sell, ↑ up-sell                           |
| Poor discovery            | ↑ Product discoverability                         |
| Distributor inefficiency  | ↑ Inventory turnover, ↑ margin                    |
| Suboptimal purchases      | ↑ Retailer basket value (AOV)                     |

---

## References

- [Online Retail Dataset, UCI ML Repo](https://archive.ics.uci.edu/ml/datasets/Online+Retail)
- [Instacart Market Basket Analysis, Kaggle](https://www.kaggle.com/datasets/instacart/market-basket-analysis)
- [Recommendation System Example (Netflix Dataset)](https://amanxai.com/2025/06/17/recommendation-system-using-python-and-tensorflow/)

---

## Contact

For questions or feedback, contact the team via GitHub Issues.
