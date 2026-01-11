# File: api_service.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np
import pandas as pd
import tensorflow as tf
import pickle
import os
# In api_service.py
# Add this function after the initial imports
def to_float32(x):
    import tensorflow as tf
    return tf.cast(x, tf.float32)
# --- Configuration & Initialization ---
MODEL_PATH = "model_artifacts/hybrid_recommender.h5"
ARTIFACTS_DIR = "model_artifacts"
VECTOR_DIM = 64
TOP_K_CANDIDATES = 500  # Number of candidates to retrieve
FINAL_LIST_SIZE = 10     # Final recommendations to display

# Business Logic Weights (Remedy C - Tunable)
W_MODEL = 0.5   # Weight for Model Relevance
W_PROFIT = 0.3  # Weight for Profit Margin
W_STOCK = 0.2   # Weight for Stock Availability (Negative influence)

# Global variables for model and data
model = None
retailer_map = {}
product_map = {}
product_vectors_data = {}
product_catalog = {}
retailer_profiles = {}

# --- Pydantic Schemas ---
class RecommendationRequest(BaseModel):
    retailer_id: str
    
class RecommendationResponse(BaseModel):
    product_id: str
    predicted_score: float
    final_rank: int

app = FastAPI(
    title="Qwipo Recommender Service",
    description="High-Performance Hybrid Recommendation API with Business Logic."
)

def load_artifacts():
    """Load model and all necessary data maps and features into memory."""
    global model, retailer_map, product_map, product_vectors_data, product_catalog, retailer_profiles
    
    # 1. Load Trained Model
    print("Loading TensorFlow Model...")
    try:
        model = tf.keras.models.load_model(
    MODEL_PATH, 
    custom_objects={'to_float32': to_float32}, 
    safe_mode=False
)
        print("Model loaded successfully.")
    except Exception as e:
        raise RuntimeError(f"Failed to load model from {MODEL_PATH}: {e}")

    # 2. Load Maps and Features
    with open(os.path.join(ARTIFACTS_DIR, 'retailer_map.pkl'), 'rb') as f:
        retailer_map = pickle.load(f)
    with open(os.path.join(ARTIFACTS_DIR, 'product_map.pkl'), 'rb') as f:
        product_map = pickle.load(f)
    with open(os.path.join(ARTIFACTS_DIR, 'product_vectors.pkl'), 'rb') as f:
        product_vectors_data = pickle.load(f)
    
    product_df = pd.read_csv(os.path.join(ARTIFACTS_DIR, 'product_catalog.csv'))
    retailer_df = pd.read_csv(os.path.join(ARTIFACTS_DIR, 'retailer_profiles.csv'))
    
    # CRITICAL FIX: Ensure categorical columns are read as integers for the model
    # The columns 'StoreType' and 'LocationTier' were encoded in data_prep.py.
    # We must treat them as integers here.
    retailer_df['StoreType'] = retailer_df['StoreType'].astype(int)
    retailer_df['LocationTier'] = retailer_df['LocationTier'].astype(int)

    # CRITICAL FIX: Ensure 'Category' is read as an integer for the product catalog
    product_df['Category'] = product_df['Category'].astype(int)


    product_catalog = product_df.set_index('ProductID').to_dict('index')
    retailer_profiles = retailer_df.set_index('RetailerID').to_dict('index')
    
    print("All artifacts loaded. Ready for inference.")

@app.on_event("startup")
async def startup_event():
    """FastAPI startup event to load model once."""
    load_artifacts()

# --- 3.1 Inference Endpoint: Candidate Generation (Microservice 1: Inference Engine) ---
@app.post("/recommend/full", response_model=list[RecommendationResponse])
async def get_hybrid_recommendations(request: RecommendationRequest):
    """Generates and re-ranks recommendations based on model relevance and business goals."""
    
    retailer_id = request.retailer_id
    if retailer_id not in retailer_map:
        raise HTTPException(status_code=404, detail="Retailer not found.")
    
    # The data loaded in load_artifacts is now guaranteed to be integers/floats
    retailer_idx = retailer_map[retailer_id]
    retailer_data = retailer_profiles[retailer_id]
    
    # Use the pre-converted integer values
    st_data_int = retailer_data['StoreType']
    lt_data_int = retailer_data['LocationTier']

    # 1. Candidate Generation (using the model on all products)
    all_product_ids = list(product_map.keys())
    # ... rest of the function remains the same ...
    all_product_indices = np.array(list(product_map.values()))
    
    # Construct input for ALL products
    num_products = len(all_product_ids)
    
    # Retailer features (repeated for all products)
    # Pass the pre-casted Python integers to np.full
    r_id_input = np.full((num_products, 1), retailer_idx, dtype=np.int32) 
    st_input = np.full((num_products, 1), st_data_int, dtype=np.int32)
    lt_input = np.full((num_products, 1), lt_data_int, dtype=np.int32)

# Product features (aligned array)
    p_id_input = all_product_indices.reshape(-1, 1).astype(np.int32)
    # Re-inserting the missing LLM vector input array
    llm_vec_input = np.array([product_vectors_data[pid] for pid in all_product_ids]) 
    
    cat_input = np.array([product_catalog[pid]['Category'] for pid in all_product_ids]).reshape(-1, 1).astype(np.int32)
    margin_input = np.array([product_catalog[pid]['ProfitMargin'] for pid in all_product_ids]).reshape(-1, 1).astype(np.float32)
    stock_input = np.array([product_catalog[pid]['CurrentStock'] for pid in all_product_ids]).reshape(-1, 1).astype(np.float32)
    
    # Run Inference
    predictions = model.predict([
        r_id_input, st_input, lt_input, 
        p_id_input, llm_vec_input, cat_input, margin_input, stock_input
    ]).flatten()
    
    # Get top 500 candidates by Model Relevance Score
    top_indices = np.argsort(predictions)[::-1][:TOP_K_CANDIDATES]
    candidate_predictions = predictions[top_indices]
    candidate_pids = [all_product_ids[i] for i in top_indices]

    print(f"Candidate Generation complete. Retrieved {len(candidate_pids)} products.")

    # 2. Re-Ranking (Step 3.3 - Business Optimization)
    final_scores = []
    
    for score, pid in zip(candidate_predictions, candidate_pids):
        p_data = product_catalog[pid]
        
        # --- Real-Time Metrics (Mocked/Fetched from Inventory Service) ---
        profit_margin = p_data['ProfitMargin'] 
        current_stock = p_data['CurrentStock'] 

        # Normalize Stock and Margin (Min-Max for simple example)
        # NOTE: In production, use a Feature Store for pre-calculated normalization bounds
        normalized_margin = (profit_margin - 0.1) / (0.4 - 0.1) 
        normalized_stock = np.clip(current_stock / 500, 0, 1) # Cap at 500 for normalization

        # Penalty for low stock (set penalty to 1 if stock is 0, 0 if stock > 50)
        stock_penalty = 1.0 if current_stock < 50 else 0.0

        # Final Business Score Formula
        final_score = (W_MODEL * score) + (W_PROFIT * normalized_margin) - (W_STOCK * stock_penalty)
        
        final_scores.append((pid, final_score, score))

    # Sort by Final Business Score
    final_scores.sort(key=lambda x: x[1], reverse=True)

    # 3. Final Output (Top 10)
    response_list = []
    for rank, (pid, final_score, model_score) in enumerate(final_scores[:FINAL_LIST_SIZE]):
        response_list.append(RecommendationResponse(
            product_id=pid,
            predicted_score=float(model_score),
            final_rank=rank + 1
        ))

    print(f"Re-Ranking complete. Top {FINAL_LIST_SIZE} list generated.")
    return response_list

# --- Run Instructions ---
# 1. Run data_prep.py
# 2. Run model_train.py
# 3. Run this service (api_service.py) using the uvicorn ASGI server:
#    uvicorn api_service:app --reload --host 0.0.0.0 --port 8000
#
# To test the API:
#    curl -X 'POST' 'http://127.0.0.1:8000/recommend/full' \
#    -H 'accept: application/json' \
#    -H 'Content-Type: application/json' \
#    -d '{"retailer_id": "R001"}'
