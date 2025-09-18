# file: reviews/topic_modeling.py
"""
LDA Topic Modeling implementation for automatic theme discovery in app reviews
Replaces basic keyword matching with unsupervised machine learning
"""

import os
import django
import sys


def setup_django():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.append(project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'deepfocal_backend.settings_local')
    django.setup()


setup_django()

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import numpy as np
import re
from collections import Counter
from .models import Review


class TopicModelingEngine:
    """
    LDA-based topic modeling for app review analysis
    """

    def __init__(self, n_topics=8, max_features=100):
        """
        Initialize the topic modeling engine

        Args:
            n_topics: Number of topics to discover
            max_features: Maximum number of features for TF-IDF
        """
        self.n_topics = n_topics
        self.max_features = max_features

        # Custom stop words for app reviews
        self.custom_stop_words = set(ENGLISH_STOP_WORDS) | {
            'app', 'application', 'phone', 'mobile', 'android', 'ios', 'iphone',
            'device', 'update', 'version', 'download', 'install', 'user', 'use',
            'using', 'used', 'like', 'really', 'just', 'good', 'bad', 'great',
            'love', 'hate', 'time', 'way', 'thing', 'getting', 'make', 'work',
            'working', 'works', 'doesnt', 'don', 'won', 'can', 'would', 'could',
            'should', 'much', 'many', 'lot', 'lots', 'pretty', 'very', 'quite',
            'review', 'rating', 'star', 'stars'
        }

        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            stop_words=list(self.custom_stop_words),
            ngram_range=(1, 2),  # Include both single words and bigrams
            min_df=2,  # Ignore terms that appear in less than 2 documents
            max_df=0.8  # Ignore terms that appear in more than 80% of documents
        )

        self.lda_model = LatentDirichletAllocation(
            n_components=self.n_topics,
            random_state=42,
            max_iter=100
        )

        self.is_fitted = False

    def preprocess_text(self, text):
        """
        Clean and preprocess review text for topic modeling
        """
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove special characters and digits, keep only letters and spaces
        text = re.sub(r'[^a-zA-Z\s]', ' ', text)

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text

    def extract_topics_from_reviews(self, reviews, sentiment_filter=None):
        """
        Extract topics from a collection of reviews

        Args:
            reviews: QuerySet or list of Review objects
            sentiment_filter: 'positive', 'negative', or None for all reviews

        Returns:
            dict: Topic analysis results
        """
        # Filter reviews by sentiment if specified
        if sentiment_filter == 'negative':
            filtered_reviews = [r for r in reviews if r.sentiment_score < -0.1]
        elif sentiment_filter == 'positive':
            filtered_reviews = [r for r in reviews if r.sentiment_score > 0.1]
        else:
            filtered_reviews = list(reviews)

        raw_review_count = len(filtered_reviews)

        if raw_review_count < 10:
            return {
                'error': f'Insufficient reviews for analysis. Found {raw_review_count} reviews.',
                'topics': [],
                'review_count': raw_review_count,
                'raw_review_count': raw_review_count,
                'usable_review_count': 0,
                'filtered_out_reviews': raw_review_count
            }

        # Preprocess review texts
        review_texts = [
            self.preprocess_text(review.content)
            for review in filtered_reviews
            if review.content
        ]

        # Remove empty texts
        review_texts = [text for text in review_texts if text.strip()]

        usable_review_count = len(review_texts)

        if usable_review_count < 10:
            return {
                'error': f'Insufficient valid review text. Found {usable_review_count} usable reviews.',
                'topics': [],
                'review_count': usable_review_count,
                'raw_review_count': raw_review_count,
                'usable_review_count': usable_review_count,
                'filtered_out_reviews': raw_review_count - usable_review_count
            }

        try:
            # Create TF-IDF matrix
            tfidf_matrix = self.vectorizer.fit_transform(review_texts)

            # Fit LDA model
            self.lda_model.fit(tfidf_matrix)
            self.is_fitted = True

            # Get feature names (words)
            feature_names = self.vectorizer.get_feature_names_out()

            # Extract topics
            topics = self._extract_topic_info(feature_names)

            # Assign topic probabilities to reviews
            doc_topic_probs = self.lda_model.transform(tfidf_matrix)

            # Find representative reviews for each topic
            topic_examples = self._find_representative_reviews(
                filtered_reviews, doc_topic_probs, review_texts
            )

            return {
                'topics': topics,
                'topic_examples': topic_examples,
                'review_count': usable_review_count,
                'raw_review_count': raw_review_count,
                'usable_review_count': usable_review_count,
                'filtered_out_reviews': raw_review_count - usable_review_count,
                'sentiment_filter': sentiment_filter,
                'model_perplexity': self.lda_model.perplexity(tfidf_matrix)
            }

        except Exception as e:
            return {
                'error': f'Topic modeling failed: {str(e)}',
                'topics': [],
                'review_count': usable_review_count,
                'raw_review_count': raw_review_count,
                'usable_review_count': usable_review_count,
                'filtered_out_reviews': raw_review_count - usable_review_count
            }

    def _extract_topic_info(self, feature_names):
        """Extract topic information from fitted LDA model"""
        topics = []

        for topic_idx, topic in enumerate(self.lda_model.components_):
            # Get top words for this topic
            top_word_indices = topic.argsort()[-10:][::-1]  # Top 10 words
            top_words = [feature_names[i] for i in top_word_indices]
            top_weights = [topic[i] for i in top_word_indices]

            # Create a meaningful topic label based on top words
            topic_label = self._generate_topic_label(top_words[:3])

            topics.append({
                'topic_id': topic_idx,
                'label': topic_label,
                'top_words': top_words,
                'word_weights': top_weights,
                'coherence_score': float(np.sum(top_weights[:5]))  # Sum of top 5 word weights
            })

        # Sort topics by coherence score (most coherent first)
        topics.sort(key=lambda x: x['coherence_score'], reverse=True)

        return topics

    def _generate_topic_label(self, top_words):
        """Generate a human-readable label for a topic based on top words"""

        # Common app review themes and their indicators
        theme_patterns = {
            'UI/Design Issues': ['interface', 'design', 'ui', 'layout', 'screen', 'display'],
            'Performance Problems': ['slow', 'lag', 'performance', 'speed', 'loading', 'crash'],
            'Login/Authentication': ['login', 'password', 'account', 'sign', 'authentication'],
            'Sync Issues': ['sync', 'synchronize', 'backup', 'data', 'lost'],
            'Feature Requests': ['feature', 'add', 'need', 'want', 'missing', 'wish'],
            'Bug Reports': ['bug', 'error', 'problem', 'issue', 'broken', 'fix'],
            'Pricing/Subscription': ['price', 'cost', 'subscription', 'premium', 'money', 'pay'],
            'Customer Support': ['support', 'help', 'customer', 'service', 'response'],
            'Usability': ['easy', 'difficult', 'confusing', 'simple', 'user friendly'],
            'Notifications': ['notification', 'alert', 'reminder', 'push']
        }

        # Check if top words match any known patterns
        top_words_set = set(top_words)

        for theme, indicators in theme_patterns.items():
            if any(indicator in word for word in top_words for indicator in indicators):
                return theme

        # If no pattern matches, create label from top words
        return ' & '.join(top_words[:2]).title()

    def _find_representative_reviews(self, reviews, doc_topic_probs, review_texts):
        """Find the most representative review for each topic"""
        topic_examples = {}

        for topic_idx in range(self.n_topics):
            # Find the review with highest probability for this topic
            topic_probs = doc_topic_probs[:, topic_idx]
            best_review_idx = np.argmax(topic_probs)

            if best_review_idx < len(reviews):
                topic_examples[topic_idx] = {
                    'review_content': reviews[best_review_idx].content[:200] + '...',
                    'probability': float(topic_probs[best_review_idx]),
                    'rating': reviews[best_review_idx].rating,
                    'sentiment_score': reviews[best_review_idx].sentiment_score
                }

        return topic_examples


def analyze_app_topics(app_id, sentiment_filter=None):
    """
    Analyze topics for a specific app

    Args:
        app_id: App identifier
        sentiment_filter: 'positive', 'negative', or None

    Returns:
        dict: Topic analysis results
    """
    # Get reviews for the app
    reviews = Review.objects.filter(app_id=app_id)

    if not reviews.exists():
        return {
            'error': f'No reviews found for app {app_id}',
            'topics': [],
            'review_count': 0
        }

    # Initialize topic modeling engine
    engine = TopicModelingEngine(n_topics=6)  # 6 topics for focused analysis

    # Extract topics
    results = engine.extract_topics_from_reviews(reviews, sentiment_filter)

    # Add app context
    results['app_id'] = app_id
    results['total_reviews'] = reviews.count()

    return results


def compare_topics_across_apps(app_ids, sentiment_filter=None):
    """
    Compare topics across multiple apps for competitive analysis

    Args:
        app_ids: List of app identifiers
        sentiment_filter: 'positive', 'negative', or None

    Returns:
        dict: Comparative topic analysis
    """
    app_results = {}

    for app_id in app_ids:
        app_results[app_id] = analyze_app_topics(app_id, sentiment_filter)

    # Find common themes across apps
    all_topics = []
    for app_id, results in app_results.items():
        if 'topics' in results:
            all_topics.extend(results['topics'])

    # Group similar topics by label
    topic_frequency = Counter(topic['label'] for topic in all_topics)
    common_themes = topic_frequency.most_common(5)

    return {
        'app_analyses': app_results,
        'common_themes': common_themes,
        'total_apps_analyzed': len(app_ids),
        'sentiment_filter': sentiment_filter
    }


# Celery task wrapper
from celery import shared_task


@shared_task
def run_topic_analysis_task(app_id, sentiment_filter=None):
    """Celery task for running topic analysis"""
    return analyze_app_topics(app_id, sentiment_filter)


@shared_task
def run_competitive_topic_analysis_task(app_ids, sentiment_filter=None):
    """Celery task for competitive topic analysis"""
    return compare_topics_across_apps(app_ids, sentiment_filter)
