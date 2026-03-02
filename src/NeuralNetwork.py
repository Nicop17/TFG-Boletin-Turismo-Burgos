import pandas as pd
import tensorflow as tf
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.metrics import classification_report, confusion_matrix
import numpy as np
import os, pickle, tqdm, re, nltk, random
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
from nltk.corpus import wordnet, stopwords
from transformers import BertTokenizer, TFBertModel

# Sinónimos
nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)
# Artículos, conjunciones, etc.
nltk.download('stopwords', quiet=True)
myStopwords = ["si", "buen", "bien", "mas"]

STOPWORDS_ES = set(stopwords.words('spanish'))
STOPWORDS_ES.update(myStopwords)

# Preprocesamiento de texto
def clean_text(text):
    text = text.lower()
    text = re.sub(r'http\S+|www\S+|https\S+', '', text)
    text = re.sub(r'\@w+|\#', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = text.strip()

    words = text.split()
    words = [word for word in words if word not in STOPWORDS_ES]
    return " ".join(words)

# Aumento de datos
def augment_text_synonym_replacement_es(text, p=0.1):
    words = text.split()
    new_words = words[:]

    # Generar la lista de palabras candidatas (sin stopwords y sin duplicados)
    unique_words = set()
    for word in words:
        if word not in STOPWORDS_ES:
            unique_words.add(word)

    candidate_words = list(unique_words)
    random.shuffle(candidate_words)

    # Determinar cuántas palabras se reemplazarán (1 a n)
    num_replaced_words = max(1, int(len(candidate_words) * p))

    # Reemplazar palabras por sinónimos
    for random_word in candidate_words[:num_replaced_words]:
        synonyms = []
        for syn in wordnet.synsets(random_word, lang='spa'):
            for lemma in syn.lemmas('spa'):
                synonym = lemma.name().replace("_", " ")
                if synonym != random_word and synonym not in synonyms:
                    synonyms.append(synonym)
        if synonyms:
            chosen_synonym = random.choice(synonyms)
            for i, w in enumerate(new_words):
                if w == random_word:
                    new_words[i] = chosen_synonym
    return " ".join(new_words)

# Cargar datos
df = pd.read_csv("trainingDataset.csv")
df = df[["text", "categoryName"]].dropna()
df["text"] = df["text"].astype(str).apply(clean_text)
df = df[df["text"] != ""]

# EDA
print("\nExploración inicial del dataset:")

# Distribución de clases
print(f"Total de muestras: {len(df)}")
print(f"Total de clases únicas: {df['categoryName'].nunique()}")
print("\nDistribución por clase:")
print(df["categoryName"].value_counts())

plt.figure(figsize=(10,6))
sns.countplot(data=df, y="categoryName", order=df["categoryName"].value_counts().index)
plt.title("Distribución de Clases")
plt.xlabel("Cantidad de muestras")
plt.ylabel("Categoría")
plt.tight_layout()
plt.show()

# Longitud de texto
df["text_length"] = df["text"].apply(lambda x: len(x.split()))

plt.figure(figsize=(10,6))
sns.histplot(df["text_length"], bins=50, kde=True)
plt.title("Distribución de Longitud de Texto (en palabras)")
plt.xlabel("Número de palabras")
plt.ylabel("Frecuencia")
plt.tight_layout()
plt.show()

max_len = df["text_length"].max()
min_len = df["text_length"].min()
print(f"\nTexto más largo tiene {max_len} palabras.")
print(f"Texto más corto tiene {min_len} palabras.")

mean_len = df["text_length"].mean()
std_len = df["text_length"].std()
print(f"Promedio de longitud de texto: {mean_len:.2f} ± {std_len:.2f} palabras.")

all_words = " ".join(df["text"]).split()
word_freq = Counter([w for w in all_words if w not in STOPWORDS_ES])
most_common_words = word_freq.most_common(15)

# Palabras más comunes
print("\nPalabras más comunes (excluyendo stopwords):")
for word, freq in most_common_words:
    print(f"{word}: {freq}")

words, freqs = zip(*most_common_words)
plt.figure(figsize=(10,6))
sns.barplot(x=list(freqs), y=list(words), palette="magma")
plt.title("Palabras Más Comunes (sin stopwords)")
plt.xlabel("Frecuencia")
plt.ylabel("Palabra")
plt.tight_layout()
plt.show()

# Codificar etiquetas
label_encoder = LabelEncoder()
df["encoded_label"] = label_encoder.fit_transform(df["categoryName"])
y_encoded = df["encoded_label"].values

# Tokenizer y modelo BERT Español
bert_model = TFBertModel.from_pretrained("dccuchile/bert-base-spanish-wwm-cased")
tokenizer = BertTokenizer.from_pretrained("dccuchile/bert-base-spanish-wwm-cased")

def get_bert_embeddings(texts, max_len=128, batch_size=16):
    embeddings = []
    for i in tqdm.tqdm(range(0, len(texts), batch_size)):
        batch = texts[i:i + batch_size]
        tokens = tokenizer(batch, padding='max_length', truncation=True,
                           max_length=max_len, return_tensors='tf')
        outputs = bert_model(**tokens)
        cls_embeddings = tf.reduce_mean(outputs.last_hidden_state, axis=1)
        embeddings.append(cls_embeddings.numpy())
    return np.concatenate(embeddings)

# División del dataset en subconjuntos
X_texts = df["text"].tolist()
X_train_text, X_test_text, y_train, y_test = train_test_split(
    X_texts, y_encoded, test_size=0.15, random_state=42, stratify=y_encoded
)

X_train_text, X_val_text, y_train, y_val = train_test_split(
    X_train_text, y_train, test_size=0.15, random_state=42, stratify=y_train
)

# Aumento de datos
augmented_X_train = list(X_train_text)
augmented_y_train = list(y_train)

for i in tqdm.tqdm(range(len(X_train_text))):
    augmented_text = augment_text_synonym_replacement_es(X_train_text[i], p=0.2)
    if augmented_text != X_train_text[i]:
        augmented_X_train.append(augmented_text)
        augmented_y_train.append(y_train[i])

# TF-IDF vectorizer
tfidf_vectorizer = TfidfVectorizer(max_features=2000, ngram_range=(1,2), min_df=5, max_df=0.8)

# Embeddings BERT y TF-IDF
X_train_bert = get_bert_embeddings(augmented_X_train)
X_train_tfidf = tfidf_vectorizer.fit_transform(augmented_X_train).toarray()
X_train_combined = np.concatenate([X_train_bert, X_train_tfidf], axis=1)

X_val_bert = get_bert_embeddings(X_val_text)
X_val_tfidf = tfidf_vectorizer.transform(X_val_text).toarray()
X_val_combined = np.concatenate([X_val_bert, X_val_tfidf], axis=1)

X_test_bert = get_bert_embeddings(X_test_text)
X_test_tfidf = tfidf_vectorizer.transform(X_test_text).toarray()
X_test_combined = np.concatenate([X_test_bert, X_test_tfidf], axis=1)

# One-hot encoding
y_train_cat = to_categorical(augmented_y_train)
y_val_cat = to_categorical(y_val)
y_test_cat = to_categorical(y_test)

# Modelo
model = Sequential([
    Dense(512, activation='relu', input_shape=(X_train_combined.shape[1],)),
    Dropout(0.3),
    Dense(64, activation='relu'),
    Dropout(0.2),
    Dense(y_train_cat.shape[1], activation='softmax')
])

optimizer = tf.keras.optimizers.Adam(learning_rate=0.00017954)

model.compile(loss='categorical_crossentropy', optimizer=optimizer, metrics=['accuracy'])

early_stop = EarlyStopping(monitor='val_loss', patience=3, restore_best_weights=True, verbose=1)
reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=1, min_lr=1e-6, verbose=1)

# Entrenamiento
history = model.fit(X_train_combined, y_train_cat,
                    validation_data=(X_val_combined, y_val_cat),
                    epochs=25,
                    batch_size=32,
                    callbacks=[early_stop, reduce_lr],
                    verbose=1)

# Evaluación
y_pred_probs = model.predict(X_test_combined)
y_pred = np.argmax(y_pred_probs, axis=1)
print(classification_report(y_test, y_pred, target_names=label_encoder.classes_))

cm = confusion_matrix(y_test, y_pred)
cm_normalized = cm.astype('float') / cm.sum(axis=1, keepdims=True)
plt.figure(figsize=(12, 10))
sns.heatmap(cm_normalized, annot=True, fmt=".2f", cmap="Blues",
            xticklabels=label_encoder.classes_,
            yticklabels=label_encoder.classes_)
plt.title("Matriz de Confusión Normalizada")
plt.xlabel("Predicción")
plt.ylabel("Clase Real")
plt.xticks(rotation=90)
plt.tight_layout()
plt.show()

# Guardar
print("\n--- Guardando modelo y componentes ---")
model.save("review_model_combined_espanol.keras")
with open("tfidf_vectorizer.pkl", "wb") as f:
    pickle.dump(tfidf_vectorizer, f)
with open("label_encoder.pkl", "wb") as f:
    pickle.dump(label_encoder, f)
with open("bert_tokenizer.pkl", "wb") as f:
    pickle.dump(tokenizer, f)