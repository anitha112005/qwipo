# File: data_prep.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow.keras.layers import TextVectorization
import pickle
import os

# --- Configuration ---
NUM_RETAILERS = 500
NUM_PRODUCTS = 1000
VECTOR_DIM = 64 # Dimension for Gemini/LLM Embeddings
MAX_SEQUENCE_LENGTH = 30 
OUTPUT_DIR = "model_artifacts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("--- 1. Generating Synthetic B2B Data ---")

# 1.1 Simulate Retailer and Product IDs
retailer_ids = [f'R{i:03d}' for i in range(NUM_RETAILERS)]
product_ids = [f'P{i:04d}' for i in range(NUM_PRODUCTS)]

# 1.2 Simulate Product Catalog (MongoDB Mock)
product_data = {
    'ProductID': product_ids,
    'Category': np.random.choice(['Dairy', 'Snacks', 'Beverages', 'Cleaning'], size=NUM_PRODUCTS),
    'Description': [f'Premium {cat} product item {i} with high demand.' for i, cat in enumerate(np.random.choice(['Dairy', 'Snacks', 'Beverages', 'Cleaning'], size=NUM_PRODUCTS))],
    'ProfitMargin': np.random.uniform(0.1, 0.4, size=NUM_PRODUCTS),
    'CurrentStock': np.random.randint(50, 500, size=NUM_PRODUCTS),
}
product_df = pd.DataFrame(product_data)

# 1.3 Simulate Retailer Profiles
retailer_df = pd.DataFrame({
    'RetailerID': retailer_ids,
    'StoreType': np.random.choice(['Supermarket', 'Convenience', 'Kiosk'], size=NUM_RETAILERS),
    'LocationTier': np.random.choice(['A', 'B', 'C'], size=NUM_RETAILERS),
})

# 1.4 Simulate LLM/Gemini Vector Embeddings (Content Features)
product_vectors = {
    pid: np.random.rand(VECTOR_DIM).astype(np.float32) 
    for pid in product_ids
}
with open(os.path.join(OUTPUT_DIR, 'product_vectors.pkl'), 'wb') as f:
    pickle.dump(product_vectors, f)
print(f"Product Vector Embeddings (size {VECTOR_DIM}) saved.")


# 1.5 Simulate Interactions (The Core Training Data)
purchases = []
for _ in range(20000): # 20,000 purchases
    retailer = np.random.choice(retailer_ids)
    product = np.random.choice(product_ids)
    purchases.append({'RetailerID': retailer, 'ProductID': product, 'Label': 1})
interactions_df = pd.DataFrame(purchases).drop_duplicates()

# 1.6 Generate Negative Samples (Crucial for Learning)
all_pairs = set((r, p) for r in retailer_ids for p in product_ids)
positive_pairs = set(zip(interactions_df['RetailerID'], interactions_df['ProductID']))
negative_pairs = list(all_pairs - positive_pairs)
np.random.shuffle(negative_pairs)

num_positives = len(interactions_df)
num_negatives_to_sample = num_positives * 10 
negative_samples = negative_pairs[:num_negatives_to_sample]

negative_df = pd.DataFrame(negative_samples, columns=['RetailerID', 'ProductID'])
negative_df['Label'] = 0

# 1.7 Final Merged and Split Dataset
data_df = pd.concat([interactions_df, negative_df]).sample(frac=1).reset_index(drop=True)
data_df = data_df.merge(retailer_df, on='RetailerID').merge(product_df.drop(columns=['Description']), on='ProductID')

# Encode Categorical Features
for col in ['StoreType', 'LocationTier', 'Category']:
    data_df[col] = data_df[col].astype('category').cat.codes

# Split data: We use a temporal split proxy by shuffling and splitting chronologically
train_df, test_df = train_test_split(data_df, test_size=0.2, random_state=42)

# --- 1.8 Save Final Artifacts (Encoded) ---

# Save training and test data (already correctly encoded)
train_df.to_csv(os.path.join(OUTPUT_DIR, 'train_data.csv'), index=False)
test_df.to_csv(os.path.join(OUTPUT_DIR, 'test_data.csv'), index=False)

# CRITICAL FIX: Save the ENCODED profiles and catalog derived from data_df
# This ensures that StoreType, LocationTier, and Category are saved as integers
final_retailer_profiles = data_df[['RetailerID', 'StoreType', 'LocationTier']].drop_duplicates()
final_retailer_profiles.to_csv(os.path.join(OUTPUT_DIR, 'retailer_profiles.csv'), index=False)

final_product_catalog = data_df[['ProductID', 'Category', 'ProfitMargin', 'CurrentStock']].drop_duplicates()
final_product_catalog.to_csv(os.path.join(OUTPUT_DIR, 'product_catalog.csv'), index=False)


# Save mappings for production serving
retailer_map = {id: i for i, id in enumerate(retailer_ids)}
product_map = {id: i for i, id in enumerate(product_ids)}
with open(os.path.join(OUTPUT_DIR, 'retailer_map.pkl'), 'wb') as f: pickle.dump(retailer_map, f)
with open(os.path.join(OUTPUT_DIR, 'product_map.pkl'), 'wb') as f: pickle.dump(product_map, f)

print(f"Data generation complete. Training size: {len(train_df)}. Test size: {len(test_df)}")
