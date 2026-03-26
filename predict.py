import sys
import ast
import pandas as pd
import numpy as np
import torch
import joblib
from transformers import AutoConfig, BertTokenizer, BertForSequenceClassification
from sklearn.base import BaseEstimator, TransformerMixin

# -----------------------------
# Config / Tokenizer
# -----------------------------
tokenizer = BertTokenizer.from_pretrained("hannahsteinbach/finetuned_parlBERT_phaseIII")
config = AutoConfig.from_pretrained("hannahsteinbach/finetuned_parlBERT_phaseIII")
id2label = config.id2label

# -----------------------------
# Preprocessing functions
# -----------------------------
columns_to_process = ["Paragraph", "Previous Paragraphs", "Supplementary Context", "Context", "Agenda Item"]

def german_transliteration(text):
    def translit(s):
        return (s.replace("ä", "ae")
                 .replace("ö", "oe")
                 .replace("ü", "ue")
                 .replace("Ä", "Ae")
                 .replace("Ö", "Oe")
                 .replace("Ü", "Ue")
                 .replace("ß", "ss"))

    if isinstance(text, list):
        return [translit(item) for item in text]
    elif isinstance(text, str):
        return translit(text)
    else:
        return text

def safe_literal_eval(x):
    if not x or pd.isna(x):
        return []
    try:
        return ast.literal_eval(x)
    except (ValueError, SyntaxError):
        return []


def preprocess_for_inference(df, use_previous=True, use_agenda=True):
    df = df.copy()
    if "Paragraph" not in df.columns:
        df["Paragraph"] = ""

    # Always create Previous Paragraphs (empty if not used)
    if "Previous Paragraphs" not in df.columns:
        df["Previous Paragraphs"] = [[] for _ in range(len(df))]

    # Only create agenda/context columns if needed
    if use_agenda:
        for col in ["Supplementary Context", "Context", "Agenda Item"]:
            if col not in df.columns:
                df[col] = ""

    # Safe literal eval
    df["Previous Paragraphs"] = df["Previous Paragraphs"].apply(safe_literal_eval)

    # Transliterate all columns that exist
    for col in ["Paragraph", "Previous Paragraphs", "Supplementary Context", "Context", "Agenda Item"]:
        if col in df.columns:
            df[f"{col}_encoded"] = df[col].apply(german_transliteration)

    return df


# -----------------------------
# Tokenization
# -----------------------------
def tokenize_multi_source(row, tokenizer, num_context=1, use_agenda_block=True, max_length=256):
    prev = row["Previous Paragraphs_encoded"]
    if isinstance(prev, str):
        prev = [prev]
    elif isinstance(prev, float) and pd.isna(prev):
        prev = []
    prev = prev[-num_context:] if num_context > 0 else []

    target = str(row["Paragraph_encoded"]) if not pd.isna(row["Paragraph_encoded"]) else ""

    agenda_block = ""
    if use_agenda_block:
        agenda_block = " ".join(
            s for s in [row.get("Supplementary Context_encoded"), row.get("Context_encoded"), row.get("Agenda Item_encoded")]
            if pd.notna(s)
        )

    all_sentences = []
    if agenda_block:
        all_sentences.append(agenda_block)
    all_sentences.extend(prev)
    all_sentences.append(target)

    input_text = " [SEP] ".join(all_sentences)

    enc = tokenizer(
        input_text,
        add_special_tokens=True,
        truncation='only_first',
        padding="max_length",
        max_length=max_length,
        return_tensors="pt"
    )

    token_type_ids = []
    for idx, sentence in enumerate(all_sentences):
        length = len(tokenizer.tokenize(sentence))
        segment_id = 1 if idx == len(all_sentences) - 1 else 0
        token_type_ids.extend([segment_id] * length)
        token_type_ids.append(segment_id)  # [SEP]

    token_type_ids = [0] + token_type_ids
    token_type_ids = (token_type_ids + [0]*max_length)[:max_length]

    return {
        "input_ids": enc["input_ids"].squeeze(),
        "attention_mask": enc["attention_mask"].squeeze(),
        "token_type_ids": torch.tensor(token_type_ids)
    }

def encode_dataframe(df, tokenizer, num_context, use_agenda_block, max_length=256):
    all_input_ids, all_attention, all_token_types = [], [], []
    for _, row in df.iterrows():
        enc = tokenize_multi_source(row, tokenizer, num_context=num_context, use_agenda_block=use_agenda_block, max_length=max_length)
        all_input_ids.append(enc["input_ids"])
        all_attention.append(enc["attention_mask"])
        all_token_types.append(enc["token_type_ids"])
    return {
        "input_ids": torch.stack(all_input_ids),
        "attention_mask": torch.stack(all_attention),
        "token_type_ids": torch.stack(all_token_types),
    }

# -----------------------------
# Interjection model preprocessing
# -----------------------------
class BooleanFeatures(BaseEstimator, TransformerMixin):
    def __init__(self, include=True):
        self.include = include
    def fit(self, X, y=None):
        return self
    def transform(self, X):
        if self.include:
            return np.column_stack([
                (X["Directed at (Party)"] != X["Party"]).astype(int),
                (X["Party"] != X["Interjector Party"]).astype(int),
                (X["Quote"]).astype(int)
            ])
        else:
            return np.zeros((X.shape[0], 2))

# -----------------------------
# Pipeline
# -----------------------------
class ParliamentaryInferencePipeline:
    def __init__(self, topic_model_name, topic_tokenizer, interjection_model, device="cuda"):
        self.device = device
        self.topic_tokenizer = topic_tokenizer
        self.topic_model = BertForSequenceClassification.from_pretrained(topic_model_name)
        self.topic_model.to(device)
        self.topic_model.eval()
        self.interjection_model = interjection_model

    def predict(self, df, predict_topics=True, predict_interjections=True, num_context=1, use_agenda_block=True):
        df = df.copy()
        if predict_topics:
            print("Predicting Topics...🏃🏽‍♀️‍➡️️")
            encodings = encode_dataframe(df, self.topic_tokenizer, num_context=num_context, use_agenda_block=use_agenda_block)
            input_ids = encodings["input_ids"].to(self.device)
            attention_mask = encodings["attention_mask"].to(self.device)
            token_type_ids = encodings["token_type_ids"].to(self.device)
            with torch.no_grad():
                outputs = self.topic_model(input_ids=input_ids,
                                           attention_mask=attention_mask,
                                           token_type_ids=token_type_ids)
            probs = torch.softmax(outputs.logits, dim=-1)
            preds = torch.argmax(probs, dim=-1)
            df["predicted_topic"] = [id2label[i] for i in preds.cpu().numpy()]

        if predict_interjections:
            print("Predicting Interjections...🏃🏽‍♀️‍➡️️")
            y_pred_binary = self.interjection_model.predict(df)
            empty = y_pred_binary.sum(axis=1) == 0
            y_pred_labels = []
            for i, row in enumerate(y_pred_binary):
                if empty[i]:
                    y_pred_labels.append(["ambiguous"]) ## if predicts nothing default to ambiguous class
                else:
                    labels = [mlb.classes_[j] for j, val in enumerate(row) if val]
                    y_pred_labels.append(labels)
            df["predicted_interjection_type"] = y_pred_labels

        return df

# -----------------------------
# CLI
# -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parliamentary Inference Pipeline")
    parser.add_argument("input_csv")
    parser.add_argument("output_csv")
    parser.add_argument("--predict_topics", action="store_true", help="Run topic prediction")
    parser.add_argument("--predict_interjections", action="store_true", help="Run interjection-type prediction")

    # Disable options to include previos paragraphs/agenda block
    parser.add_argument("--no_previous_paragraphs", action="store_true", help="Disable including previous paragraphs")
    parser.add_argument("--no_agenda_block", action="store_true", help="Disable including agenda/context block")

    args = parser.parse_args()

    df = pd.read_csv(args.input_csv)
    df = preprocess_for_inference(
        df,
        use_previous=not args.no_previous_paragraphs,
        use_agenda=not args.no_agenda_block
    )

    for col in ["Directed at (Party)", "Party", "Interjector Party", "Quote"]:
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].fillna("")

    df["Interjection Text"] = df["Interjection Text"].fillna("")
    df["Paragraph"] = df["Paragraph"].fillna("")

    interjection_model = joblib.load("interjections/interjection_type_svm_pipeline.joblib")
    mlb = joblib.load("interjections/interjection_type_mlb.joblib")

    pipeline = ParliamentaryInferencePipeline(
        topic_model_name="hannahsteinbach/finetuned_parlBERT_phaseIII",
        topic_tokenizer=tokenizer,
        interjection_model=interjection_model,
        device="cuda" if torch.cuda.is_available() else "cpu"
    )

    # Defaults for topic prediction
    if args.predict_topics:
        # Default values
        num_context = 1  # include 1 previous paragraph by default
        use_agenda_block = True  # include agenda/context by default

        # Apply user overrides if flags are set
        if args.no_previous_paragraphs:
            num_context = 0
        if args.no_agenda_block:
            use_agenda_block = False
    else:
        # Topic prediction not requested, context doesn’t matter
        num_context = 0
        use_agenda_block = False

    # Run pipeline
    annotated_df = pipeline.predict(
        df,
        predict_topics=args.predict_topics,
        predict_interjections=args.predict_interjections,
        num_context=num_context,
        use_agenda_block=use_agenda_block
    )

    annotated_df.to_csv(args.output_csv, index=False)