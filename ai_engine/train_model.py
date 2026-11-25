import pandas as pd
import joblib

from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report


BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "lead_dataset.csv"
MODEL_PATH = BASE_DIR / "lead_model.pkl"


# Load dataset
data = pd.read_csv(DATA_PATH)

# Input features
X = data[
    [
        'customer_visits',
        'days_since_last_visit',
        'followups',
        'interest_level',
        'product_price'
    ]
]

# Target
y = data['purchased']

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.25,
    random_state=42,
    stratify=y
)

# Train model
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42,
    class_weight='balanced'
)

model.fit(X_train, y_train)

# Evaluate
predictions = model.predict(X_test)

accuracy = accuracy_score(y_test, predictions)

print("Model Training Completed")
print("Accuracy:", accuracy)

print("\nClassification Report:")
print(classification_report(
    y_test,
    predictions,
    zero_division=0
))

# Save model
joblib.dump(model, MODEL_PATH)

print("\nModel saved at:", MODEL_PATH)