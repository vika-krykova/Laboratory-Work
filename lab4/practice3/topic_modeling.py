import argparse
import json
import re
import os

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import ftfy
import pymorphy3
import pyLDAvis
import pyLDAvis.gensim_models as gensimvis

from wordcloud import WordCloud
from gensim import corpora, models
from gensim.models.coherencemodel import CoherenceModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF
from sklearn.cluster import KMeans

morph = pymorphy3.MorphAnalyzer()

STOP_WORDS = set("""
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только 
ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или 
ни быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они 
тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе 
под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один почти 
мой тем чтобы нее сейчас были куда зачем сказать всех никогда сегодня можно при 
наконец два об другой хоть после над больше тот через эти нас про всего них какая 
много разве три эту моя впрочем хорошо свою этой перед иногда лучше чуть том нельзя 
такой им более всегда конечно всю между
""".split())

def load_data(dataset_name):
    texts = []
    
    if dataset_name == 'mixed':
        filepath = 'mixed.json'
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Файл {filepath} не найден. Сначала создайте его.")
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for item in data:
            text = f"{item.get('title', '')} {item.get('summary', '')} {item.get('description', '')}"
            texts.append(text)
            
    else:
        filepath = 'news.json' if dataset_name == 'news' else 'products.json'
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Файл {filepath} не найден в текущей папке.")

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data:
            if dataset_name == 'news':
                text = f"{item.get('title', '')} {item.get('summary', '')}"
            else:
                text = f"{item.get('title', '')} {item.get('description', '')}"
            texts.append(text)

    initial_len = len(texts)
    texts = list(dict.fromkeys(texts))
    print(f"Загружено {initial_len} документов, после дедупликации осталось {len(texts)}")
    
    return texts

def preprocess_text(text):
    if not isinstance(text, str) or not text.strip():
        return []
    
    text = ftfy.fix_text(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[^а-яёА-ЯЁa-zA-Z]', ' ', text)
    tokens = text.lower().split()
    
    lemmas = []
    for word in tokens:
        if len(word) > 2 and word not in STOP_WORDS:
            lemma = morph.parse(word)[0].normal_form
            lemmas.append(lemma)
            
    return lemmas

def compute_coherence(texts_tokens, dictionary, model, method='c_v'):
    coherence_model = CoherenceModel(model=model, texts=texts_tokens, dictionary=dictionary, coherence=method)
    return coherence_model.get_coherence()

def run_lda(processed_texts, num_topics):
    dictionary = corpora.Dictionary(processed_texts)
    dictionary.filter_extremes(no_below=2, no_above=0.9)
    corpus = [dictionary.doc2bow(text) for text in processed_texts]
    
    lda_model = models.LdaModel(
        corpus=corpus, 
        id2word=dictionary, 
        num_topics=num_topics, 
        random_state=42, 
        passes=15,
        alpha='auto',
        eta='auto'
    )
    
    coherence = compute_coherence(processed_texts, dictionary, lda_model)
    
    topics_with_weights = []
    for idx, topic in lda_model.show_topics(num_topics=-1, num_words=10, formatted=False):
        topic_words = [{"word": word, "weight": float(weight)} for word, weight in topic]
        topics_with_weights.append(topic_words)
        
    doc_topic_matrix = []
    for doc_bow in corpus:
        doc_topics = lda_model.get_document_topics(doc_bow, minimum_probability=0)
        doc_topics = sorted(doc_topics, key=lambda x: x[0])
        doc_topic_matrix.append([prob for topic_id, prob in doc_topics])
        
    return lda_model, coherence, topics_with_weights, corpus, dictionary, doc_topic_matrix

def run_nmf(processed_texts_str, processed_texts_tokens, num_topics):
    tfidf_vectorizer = TfidfVectorizer(max_features=1000, min_df=2, max_df=0.9)
    tfidf = tfidf_vectorizer.fit_transform(processed_texts_str)
    
    nmf_model = NMF(n_components=num_topics, random_state=42, max_iter=500)
    W = nmf_model.fit_transform(tfidf)
    H = nmf_model.components_
    
    feature_names = tfidf_vectorizer.get_feature_names_out()
    
    topics_with_weights = []
    topics_words_only = []
    for topic_idx, topic in enumerate(H):
        top_features_ind = topic.argsort()[:-10 - 1:-1]
        topic_words = [{"word": feature_names[i], "weight": float(topic[i])} for i in top_features_ind]
        topics_with_weights.append(topic_words)
        topics_words_only.append([feature_names[i] for i in top_features_ind])
        
    dictionary = corpora.Dictionary(processed_texts_tokens)
    coherence_model = CoherenceModel(
        topics=topics_words_only, 
        texts=processed_texts_tokens, 
        dictionary=dictionary, 
        coherence='c_v'
    )
    coherence = coherence_model.get_coherence()
        
    return nmf_model, coherence, topics_with_weights, W

def plot_top_words(topics_with_weights, title, output_path):
    num_topics = len(topics_with_weights)
    fig, axes = plt.subplots(1, num_topics, figsize=(20, 6), sharey=True)
    if num_topics == 1:
        axes = [axes]
        
    for i, (topic_data, ax) in enumerate(zip(topics_with_weights, axes)):
        words = [item['word'] for item in topic_data][::-1]
        weights = [item['weight'] for item in topic_data][::-1]
        
        ax.barh(words, weights)
        ax.set_title(f"Топик {i+1}")
        ax.invert_yaxis()
        
    plt.suptitle(title, fontsize=16)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Визуализация топ-слов сохранена: {output_path}")

def generate_wordcloud(topic_data, title, output_path):
    freq = {item['word']: item['weight'] for item in topic_data}
    wc = WordCloud(width=800, height=400, background_color='white').generate_from_frequencies(freq)
    
    plt.figure(figsize=(10, 5))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Облако слов сохранено: {output_path}")

def plot_coherence(coherence_scores, output_path):
    K = list(coherence_scores.keys())
    scores = list(coherence_scores.values())
    
    plt.figure(figsize=(10, 5))
    plt.plot(K, scores, marker='o', color='b')
    plt.title("Выбор количества топиков (Coherence Score)")
    plt.xlabel("Число топиков (K)")
    plt.ylabel("Coherence Score (c_v)")
    plt.grid(True)
    
    best_k = K[np.argmax(scores)]
    best_score = max(scores)
    plt.axvline(x=best_k, color='r', linestyle='--', label=f'Оптимум K={best_k} (Score: {best_score:.4f})')
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"График Coherence сохранен: {output_path}")

def cluster_documents(doc_topic_matrix, num_clusters=3):
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(doc_topic_matrix)
    return clusters

def main():
    parser = argparse.ArgumentParser(description="Тематическое моделирование")
    parser.add_argument("--dataset", required=True, choices=['news', 'products', 'mixed'], help="Датасет")
    parser.add_argument("--method", choices=['lda', 'nmf', 'both'], help="Метод")
    parser.add_argument("--compare", action="store_true", help="Сравнить LDA и NMF")
    parser.add_argument("--topics", default="10", help="Число топиков или 'auto'")
    parser.add_argument("--output", required=True, help="Префикс для файлов")
    args = parser.parse_args()

    if args.compare:
        args.method = 'both'
    if not args.method:
        parser.error("Укажите --method или --compare")

    raw_texts = load_data(args.dataset)
    
    print("Предобработка (NLP)...")
    processed_tokens = [preprocess_text(t) for t in raw_texts]
    processed_strings = [" ".join(tokens) for tokens in processed_tokens]
    
    valid_indices = [i for i, tokens in enumerate(processed_tokens) if len(tokens) > 0]
    processed_tokens = [processed_tokens[i] for i in valid_indices]
    processed_strings = [processed_strings[i] for i in valid_indices]
    
    if len(processed_tokens) < 10:
        print("ОШИБКА: Слишком мало валидных документов.")
        return

    print(f"Осталось {len(processed_tokens)} валидных документов.")

    lda_coh, nmf_coh = None, None

    if args.topics == 'auto':
        print("Режим AUTO: Подбор количества топиков...")
        coherence_scores = {}
        dictionary = corpora.Dictionary(processed_tokens)
        dictionary.filter_extremes(no_below=2, no_above=0.9)
        corpus = [dictionary.doc2bow(text) for text in processed_tokens]
        
        for k in range(3, 21):
            print(f"  Обучение LDA для K={k}...")
            lda = models.LdaModel(corpus=corpus, id2word=dictionary, num_topics=k, passes=5, random_state=42)
            coh = compute_coherence(processed_tokens, dictionary, lda)
            coherence_scores[k] = coh
            print(f"    Coherence: {coh:.4f}")
            
        plot_coherence(coherence_scores, f"{args.output}_coherence.png")
        best_k = max(coherence_scores, key=coherence_scores.get)
        print(f"\nЛучшее K по coherence: {best_k}")
        num_topics = best_k
    else:
        num_topics = int(args.topics)

    if args.method in ['lda', 'both']:
        print(f"\nОбучение LDA (K={num_topics})...")
        lda_model, lda_coh, lda_topics, lda_corpus, lda_dict, lda_doc_topic = run_lda(processed_tokens, num_topics)
        print(f"LDA Coherence: {lda_coh:.4f}")
        
        with open(f"{args.output}_lda_topics.json", "w", encoding="utf-8") as f:
            json.dump(lda_topics, f, ensure_ascii=False, indent=2)
            
        df_lda = pd.DataFrame(lda_doc_topic)
        clusters_lda = cluster_documents(lda_doc_topic, num_clusters=3)
        df_lda['cluster'] = clusters_lda
        df_lda.to_csv(f"{args.output}_lda_doc_topic.csv", index=False)
        
        plot_top_words(lda_topics, f"LDA: Топ-слова (K={num_topics})", f"{args.output}_lda_top_words.png")
        generate_wordcloud(lda_topics[0], f"LDA: Облако слов для Топика 1", f"{args.output}_lda_wordcloud.png")
        
        try:
            vis_data = gensimvis.prepare(lda_model, lda_corpus, lda_dict)
            pyLDAvis.save_html(vis_data, f"{args.output}_lda_vis.html")
            print(f"Интерактивная pyLDAvis визуализация сохранена: {args.output}_lda_vis.html")
        except Exception as e:
            print(f"Не удалось создать pyLDAvis HTML: {e}")

    if args.method in ['nmf', 'both']:
        print(f"\nОбучение NMF (K={num_topics})...")
        nmf_model, nmf_coh, nmf_topics, nmf_doc_topic = run_nmf(processed_strings, processed_tokens, num_topics)
        print(f"NMF Coherence: {nmf_coh:.4f}")
        
        with open(f"{args.output}_nmf_topics.json", "w", encoding="utf-8") as f:
            json.dump(nmf_topics, f, ensure_ascii=False, indent=2)
            
        df_nmf = pd.DataFrame(nmf_doc_topic)
        clusters_nmf = cluster_documents(nmf_doc_topic, num_clusters=3)
        df_nmf['cluster'] = clusters_nmf
        df_nmf.to_csv(f"{args.output}_nmf_doc_topic.csv", index=False)
        
        plot_top_words(nmf_topics, f"NMF: Топ-слова (K={num_topics})", f"{args.output}_nmf_top_words.png")

    if args.method == 'both' and lda_coh is not None and nmf_coh is not None:
        print("\n" + "="*40)
        print("ИТОГОВОЕ СРАВНЕНИЕ МЕТОДОВ")
        print("="*40)
        print(f"LDA Coherence: {lda_coh:.4f}")
        print(f"NMF Coherence: {nmf_coh:.4f}")
        
        if lda_coh > nmf_coh:
            print("Победитель по Coherence: LDA (разница: {:.4f})".format(lda_coh - nmf_coh))
        else:
            print("Победитель по Coherence: NMF (разница: {:.4f})".format(nmf_coh - lda_coh))
        print("="*40)

    print("\nГотово! Все артефакты сохранены.")

if __name__ == "__main__":
    main()