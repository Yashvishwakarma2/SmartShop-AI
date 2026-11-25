import joblib

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / "lead_model.pkl"

model = joblib.load(MODEL_PATH)


def predict_lead(
    customer_visits,
    days_since_last_visit,
    followups,
    interest_level,
    product_price
):

    features = [[
        customer_visits,
        days_since_last_visit,
        followups,
        interest_level,
        product_price
    ]]

    probability = model.predict_proba(features)[0][1]

    prediction = "High Purchase Chance" if probability >= 0.5 else "Low Purchase Chance"

    score = round(probability * 100, 2)

    return {
        'prediction': prediction,
        'probability': score
    }