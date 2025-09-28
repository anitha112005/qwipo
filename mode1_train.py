# File: model_train.py
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Model, save_model
from tensorflow.keras.layers import Input, Embedding, Concatenate, Dense, Dropout,Lambda
import pickle
import os
# Inside model_train.py, define this function near the top
def to_float32(x):
    import tensorflow as tf # Required to ensure 'tf' is available inside the function context
    return tf.cast(x, tf.float32)
OUTPUT_DIR = "model_artifacts"
MODEL_PATH = os.path.join(OUTPUT_DIR, 'hybrid_recommender.h5')
VECTOR_DIM = 64
EMBEDDING_DIM = 32

# --- Load Data and Artifacts ---
train_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'train_data.csv'))
test_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'test_data.csv'))
product_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'product_catalog.csv'))

with open(os.path.join(OUTPUT_DIR, 'retailer_map.pkl'), 'rb') as f:
    retailer_map = pickle.load(f)
with open(os.path.join(OUTPUT_DIR, 'product_map.pkl'), 'rb') as f:
    product_map = pickle.load(f)
with open(os.path.join(OUTPUT_DIR, 'product_vectors.pkl'), 'rb') as f:
    product_vectors_data = pickle.load(f)

# --- Pre-calculate Inputs ---
NUM_RETAILERS = len(retailer_map)
NUM_PRODUCTS = len(product_map)

# Create a matrix of the LLM/Gemini vectors for the Product Tower
product_vector_matrix = np.array([product_vectors_data[pid] for pid in product_map.keys()])
# Align features for the Product Tower: ProfitMargin and CurrentStock
product_features = product_df[['ProductID', 'Category', 'ProfitMargin', 'CurrentStock']].set_index('ProductID')

print(f"--- 2. Building Two-Tower Hybrid Model ---")

# --- 2.1 Retailer Tower (User/Query Tower) ---
retailer_input = Input(shape=(1,), name='retailer_id_input')

# Retailer Feature Inputs (B2B Context) - MUST BE DEFINED HERE
store_type_input = Input(shape=(1,), name='store_type_input')
location_tier_input = Input(shape=(1,), name='location_tier_input')

# Retailer ID Embedding (Collaborative Filtering Component)
retailer_embedding = Embedding(input_dim=NUM_RETAILERS, output_dim=EMBEDDING_DIM, name='retailer_embedding')(retailer_input)
retailer_flat = tf.keras.layers.Flatten()(retailer_embedding)

# Cast features to float and define output shape for compatibility
# Replace the two lines starting with 'store_type_float' and 'location_tier_float'
store_type_float = tf.keras.layers.Lambda(to_float32, output_shape=(1,))(store_type_input)
location_tier_float = tf.keras.layers.Lambda(to_float32, output_shape=(1,))(location_tier_input)

# Concatenate Retailer ID embedding with B2B context features
retailer_vector = Concatenate()([retailer_flat, store_type_float, location_tier_float])
retailer_output = Dense(EMBEDDING_DIM, activation='relu', name='retailer_output')(retailer_vector)


# --- 2.2 Product Tower (Item/Candidate Tower) ---
product_input = Input(shape=(1,), name='product_id_input')
# Product ID Embedding (Collaborative Filtering Component)
product_embedding = Embedding(input_dim=NUM_PRODUCTS, output_dim=EMBEDDING_DIM, name='product_embedding')(product_input)
product_flat = tf.keras.layers.Flatten()(product_embedding)

# Product Content Vector (Gemini/LLM Feature - Remedy B)
# We use a static layer to integrate the pre-calculated LLM vectors
llm_vector_input = Input(shape=(VECTOR_DIM,), name='llm_vector_input')

# Product Feature Inputs (Business Context)
category_input = Input(shape=(1,), name='category_input')
margin_input = Input(shape=(1,), name='margin_input')
stock_input = Input(shape=(1,), name='stock_input')

# Replace the three lines inside Concatenate() starting with 'Lambda'
# Concatenate Product ID embedding with all Content and Business features
product_vector = Concatenate()([
    product_flat, 
    llm_vector_input, 
    tf.keras.layers.Lambda(to_float32, output_shape=(1,))(category_input),
    tf.keras.layers.Lambda(to_float32, output_shape=(1,))(margin_input),   
    tf.keras.layers.Lambda(to_float32, output_shape=(1,))(stock_input)     
])
product_output = Dense(EMBEDDING_DIM, activation='relu', name='product_output')(product_vector)



# --- 2.3 Final Prediction Layer (Dot Product) ---
# The two final vectors are multiplied and run through a final network to get a relevance score
dot_product = tf.keras.layers.Dot(axes=1)([retailer_output, product_output])
output = Dense(1, activation='sigmoid', name='prediction_output')(dot_product)

# --- 2.4 Model Definition ---
model = Model(
    inputs=[
        retailer_input, store_type_input, location_tier_input, 
        product_input, llm_vector_input, category_input, margin_input, stock_input
    ],
    outputs=output
)

# --- 2.5 Training ---
model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy', tf.keras.metrics.AUC()])

# Prepare Tensors for Training
X_train = {
    'retailer_id_input': train_df['RetailerID'].map(retailer_map).values,
    'store_type_input': train_df['StoreType'].values,
    'location_tier_input': train_df['LocationTier'].values,
    'product_id_input': train_df['ProductID'].map(product_map).values,
    'llm_vector_input': np.stack([product_vectors_data[pid] for pid in train_df['ProductID']]),
    'category_input': train_df['Category'].values,
    'margin_input': train_df['ProfitMargin'].values,
    'stock_input': train_df['CurrentStock'].values,
}
y_train = train_df['Label'].values

model.fit(X_train, y_train, epochs=5, batch_size=256, verbose=1)

# --- 2.6 Saving Model (Fixed for Keras 3 custom object handling) ---

# We remove the unsupported 'custom_objects' argument and rely on 'api_service.py' 
# to provide it during loading.
model.save(MODEL_PATH, save_format='h5', include_optimizer=False)

print(f"Model saved successfully to {MODEL_PATH}")
