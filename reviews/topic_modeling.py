# file: reviews/topic_modeling.py
"""
LDA Topic Modeling implementation for automatic theme discovery in app reviews
Replaces basic keyword matching with unsupervised machine learning
"""

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import numpy as np
import re
from collections import Counter, defaultdict
from .models import Review
from .app_id_utils import expand_app_ids

class TopicModelingEngine:
    """
    LDA-based topic modeling for app review analysis
    """

    def __init__(self, n_topics=10, max_features=500):
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
            'review', 'rating', 'star', 'stars', 'spotify',
            'listen', 'listening', 'play', 'playing'
        }

        self.vectorizer = CountVectorizer(
            max_features=self.max_features,
            stop_words=list(self.custom_stop_words),
            ngram_range=(1, 3),  # Include single words, bigrams, and trigrams
            min_df=5,  # Ignore terms that appear in less than 5 documents
            max_df=0.5  # Ignore terms that appear in more than 50% of documents
        )

        self.lda_model = LatentDirichletAllocation(
            n_components=self.n_topics,
            random_state=42,
            max_iter=200,
            doc_topic_prior=0.05,
            topic_word_prior=0.005,
            learning_method='batch',
            evaluate_every=10
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
            filtered_reviews = [
                r for r in reviews
                if (
                    (r.sentiment_score is not None and r.sentiment_score < 0)
                    or (r.sentiment_score is None and r.rating is not None and r.rating <= 3)
                    or (r.rating is not None and r.rating <= 2)
                )
            ]
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
            distinct_topics = self._select_distinct_topics(topics, max_topics=self.n_topics)

            # Assign topic probabilities to reviews
            doc_topic_probs = self.lda_model.transform(tfidf_matrix)

            # Calculate how many reviews primarily map to each topic
            topic_mentions = Counter()
            topic_probability_sums = defaultdict(float)

            for prob_vector in doc_topic_probs:
                if prob_vector.size == 0:
                    continue

                primary_topic = int(np.argmax(prob_vector))
                primary_probability = float(prob_vector[primary_topic])

                topic_mentions[primary_topic] += 1
                topic_probability_sums[primary_topic] += primary_probability

            topic_stats = {}
            for topic in topics:
                topic_id = topic['topic_id']
                mentions = int(topic_mentions.get(topic_id, 0))
                average_probability = (
                    topic_probability_sums[topic_id] / mentions
                    if mentions > 0
                    else 0.0
                )
                mention_percentage = (
                    round((mentions / usable_review_count) * 100, 1)
                    if usable_review_count > 0
                    else 0.0
                )

                topic['mentions'] = mentions
                topic['mention_percentage'] = mention_percentage
                topic['average_probability'] = round(average_probability, 4)

                topic_stats[topic_id] = {
                    'mentions': mentions,
                    'mention_percentage': mention_percentage,
                    'average_probability': round(average_probability, 4),
                }

            # Find representative reviews for each topic
            topic_examples = self._find_representative_reviews(
                filtered_reviews, doc_topic_probs, review_texts, topics
            )

            return {
                'topics': topics,
                'distinct_topics': distinct_topics,
                'topic_examples': topic_examples,
                'topic_stats': topic_stats,
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
                'distinct_topics': [],
                'review_count': usable_review_count,
                'raw_review_count': raw_review_count,
                'usable_review_count': usable_review_count,
                'filtered_out_reviews': raw_review_count - usable_review_count
            }

    def _extract_topic_info(self, feature_names):
        """Extract topic information from fitted LDA model"""
        topics = []
        used_labels = set()

        for topic_idx, topic in enumerate(self.lda_model.components_):
            # Get top words for this topic
            top_word_indices = topic.argsort()[-10:][::-1]  # Top 10 words
            top_words = [feature_names[i] for i in top_word_indices]
            top_weights = [topic[i] for i in top_word_indices]

            # Create a meaningful topic label based on top words
            topic_label, label_keywords, label_excludes = self._generate_topic_label(top_words[:5], used_labels)

            topics.append({
                'topic_id': topic_idx,
                'label': topic_label,
                'top_words': top_words,
                'label_keywords': list(label_keywords) if label_keywords else [],
                'label_excluded_keywords': list(label_excludes) if label_excludes else [],
                'word_weights': top_weights,
                'coherence_score': float(np.sum(top_weights[:5]))  # Sum of top 5 word weights
            })

        # Sort topics by coherence score (most coherent first)
        topics.sort(key=lambda x: x['coherence_score'], reverse=True)

        return topics

    def _select_distinct_topics(self, topics, max_topics=3):
        if not topics:
            return []

        selected = []
        skipped = []

        for topic in topics:
            current_words = set(topic.get('top_words', [])[:5])

            if not current_words:
                continue

            is_similar = False
            for chosen in selected:
                chosen_words = set(chosen.get('top_words', [])[:5])
                if not chosen_words:
                    continue

                intersection = len(current_words & chosen_words)
                union = len(current_words | chosen_words)
                similarity = intersection / union if union else 0

                if similarity >= 0.6:
                    is_similar = True
                    break

            # Avoid duplicate base labels (ignore parenthetical descriptors)
            candidate_base = topic.get('label', '').split('(')[0].strip().lower()
            if any(chosen.get('label', '').split('(')[0].strip().lower() == candidate_base for chosen in selected):
                is_similar = True

            if is_similar:
                skipped.append(topic)
                continue

            selected.append(topic)

            if len(selected) >= max_topics:
                break

        if len(selected) < max_topics:
            remaining_slots = max_topics - len(selected)
            for topic in skipped:
                candidate_base = topic.get('label', '').split('(')[0].strip().lower()
                if any(chosen.get('label', '').split('(')[0].strip().lower() == candidate_base for chosen in selected):
                    continue
                selected.append(topic)
                if len(selected) >= max_topics:
                    break

        return selected

    def _generate_topic_label(self, top_words, used_labels=None):
        """Generate a human-readable label for a topic based on top words"""

        theme_patterns = [
            {
                'name': 'Music Discovery & Recommendations',
                'keywords': {'discover', 'recommend', 'recommendation', 'algorithm', 'radio', 'mix', 'weekly', 'daily mix', 'curation', 'suggested', 'release radar', 'made for'},
                'exclude': {'ad', 'ads', 'premium', 'price', 'pay'},
                'priority': 7,
            },
            {
                'name': 'Playlist & Library Management',
                'keywords': {'playlist', 'playlists', 'library', 'save', 'saved', 'collection', 'organize', 'add to playlist', 'curate', 'folders'},
                'exclude': {'ad', 'ads', 'premium', 'price', 'pay'},
                'priority': 6,
            },
            {
                'name': 'Playback & Shuffle Control',
                'keywords': {'shuffle', 'skip', 'skipping', 'queue', 'order', 'playback', 'repeat', 'sequence', 'auto play', 'autoplay', 'next', 'previous'},
                'exclude': {'ad', 'ads', 'premium', 'price', 'pay'},
                'priority': 6,
            },
            {
                'name': 'Ads & Paywall Issues',
                'keywords': {'ads', 'ad', 'advert', 'commercial', 'sponsor', 'premium', 'paywall', 'interrupt'},
                'exclude': set(),
                'priority': 4,
            },
            {
                'name': 'Pricing & Value',
                'keywords': {'price', 'pricing', 'cost', 'billing', 'payment', 'pay', 'money', 'subscription', 'value', 'expensive', 'worth', 'plan'},
                'exclude': set(),
                'priority': 5,
            },
            {
                'name': 'Content Availability',
                'keywords': {'missing', 'unavailable', 'available', 'removed', 'catalog', 'artist', 'album', 'track', 'region', 'country', 'content', 'rights'},
                'exclude': {'ad', 'ads', 'premium', 'price', 'pay'},
                'priority': 4,
            },
            {
                'name': 'Offline & Downloads',
                'keywords': {'download', 'offline', 'downloaded', 'cache', 'storage'},
                'exclude': set(),
                'priority': 4,
            },
            {
                'name': 'Login & Authentication',
                'keywords': {'login', 'log', 'account', 'password', 'sign', 'authentication', 'verify'},
                'exclude': set(),
                'priority': 5,
            },
            {
                'name': 'Performance & Stability',
                'keywords': {'slow', 'lag', 'laggy', 'performance', 'loading', 'crash', 'freeze', 'freezing', 'glitch', 'stutter', 'buffer'},
                'exclude': set(),
                'priority': 5,
            },
            {
                'name': 'Bugs & Errors',
                'keywords': {'bug', 'bugs', 'error', 'issue', 'broken', 'fix', 'glitch', 'problem'},
                'exclude': set(),
                'priority': 4,
            },
            {
                'name': 'Customer Support',
                'keywords': {'support', 'help', 'customer', 'service', 'response'},
                'exclude': set(),
                'priority': 3,
            },
            {
                'name': 'User Interface & Navigation',
                'keywords': {'interface', 'ui', 'design', 'layout', 'navigation', 'screen', 'display'},
                'exclude': set(),
                'priority': 3,
            },
            {
                'name': 'Feature Requests',
                'keywords': {'feature', 'features', 'add', 'need', 'missing', 'wish', 'should'},
                'exclude': set(),
                'priority': 2,
            },
        ]

        scored_patterns = []
        matched_keyword_sets = {}
        matched_exclusion_sets = {}
        for pattern in theme_patterns:
            match_count = sum(
                1 for word in top_words
                if any(indicator in word for indicator in pattern['keywords'])
            )
            if match_count > 0:
                scored_patterns.append((match_count, pattern['priority'], pattern['name']))
                matched_keyword_sets[pattern['name']] = pattern['keywords']
                matched_exclusion_sets[pattern['name']] = pattern.get('exclude', set())

        candidate_label = None
        candidate_keywords = set()
        candidate_excludes = set()

        if scored_patterns:
            scored_patterns.sort(key=lambda item: (item[0], item[1]), reverse=True)
            normalized_used = {label.lower(): label for label in (used_labels or [])}

            for _, _, theme_name in scored_patterns:
                if theme_name.lower() not in normalized_used:
                    candidate_label = theme_name
                    candidate_keywords = matched_keyword_sets.get(theme_name, set())
                    candidate_excludes = matched_exclusion_sets.get(theme_name, set())
                    break

            if candidate_label is None:
                candidate_label = scored_patterns[0][2]
                candidate_keywords = matched_keyword_sets.get(candidate_label, set())
                candidate_excludes = matched_exclusion_sets.get(candidate_label, set())

        if not candidate_label:
            candidate_label = ' & '.join(word.title() for word in top_words[:2] if word)
            if not candidate_label:
                candidate_label = 'General Feedback'
            candidate_keywords = set()
            candidate_excludes = set()

        if used_labels is not None:
            normalized_used = {label.lower(): label for label in used_labels}
            normalized_candidate = candidate_label.lower()

            if normalized_candidate in normalized_used:
                meaningful_words = [
                    word.title()
                    for word in top_words
                    if word
                    and word.lower() not in normalized_candidate
                    and len(word) > 3
                ]

                for word_title in meaningful_words:
                    alt_label = f"{candidate_label} ({word_title})"
                    if alt_label.lower() not in normalized_used:
                        candidate_label = alt_label
                        candidate_keywords = candidate_keywords | {word_title.lower()}
                        break
                else:
                    suffix = top_words[0].title() if top_words else str(len(used_labels) + 1)
                    candidate_label = f"{candidate_label} ({suffix})"
                    candidate_keywords = candidate_keywords | {suffix.lower()}

            used_labels.add(candidate_label)

        return candidate_label, candidate_keywords, candidate_excludes

    def _find_representative_reviews(self, reviews, doc_topic_probs, review_texts, topics):
        """Find the most representative reviews for each topic"""
        topic_examples = {}

        topics_by_id = {topic['topic_id']: topic for topic in topics}
        seen_quotes = set()

        for topic_idx in range(self.n_topics):
            topic_probs = doc_topic_probs[:, topic_idx]
            if topic_probs.size == 0:
                continue

            top_indices = np.argsort(topic_probs)[::-1]

            topic_info = topics_by_id.get(topic_idx, {})
            topic_words = topic_info.get('top_words', [])
            label_terms = [
                term.lower()
                for term in topic_info.get('label_keywords', [])
                if term and len(term) > 3
            ]
            label_excludes = [
                term.lower()
                for term in topic_info.get('label_excluded_keywords', [])
                if term and len(term) > 2
            ]
            fallback_terms = [
                term.lower()
                for term in topic_words[:6]
                if term and len(term) > 3
            ]

            examples = []
            for review_idx in top_indices:
                if review_idx >= len(reviews):
                    continue

                review_obj = reviews[review_idx]
                quote = (review_obj.content or '').strip()
                if not quote:
                    continue

                lowered_quote = quote.lower()
                terms_to_check = label_terms if label_terms else fallback_terms
                if terms_to_check and not any(term in lowered_quote for term in terms_to_check):
                    continue

                if label_excludes and any(term in lowered_quote for term in label_excludes):
                    continue

                topic_distribution = doc_topic_probs[review_idx]
                if topic_distribution.size > 1:
                    sorted_probs = np.sort(topic_distribution)[::-1]
                    dominance = sorted_probs[0] - sorted_probs[1]
                else:
                    dominance = topic_probs[review_idx]

                if dominance < 0.08:
                    continue

                if quote in seen_quotes:
                    continue

                seen_quotes.add(quote)

                examples.append({
                    'quote': quote,
                    'probability': float(topic_probs[review_idx]),
                    'rating': review_obj.rating,
                    'sentiment_score': review_obj.sentiment_score
                })

                if len(examples) >= 2:
                    break

            if examples:
                topic_examples[topic_idx] = examples

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
    app_ids = expand_app_ids(app_id)
    reviews = Review.objects.filter(app_id__in=app_ids, counts_toward_score=True)

    if not reviews.exists():
        return {
            'error': f'No reviews found for app {app_id}',
            'topics': [],
            'review_count': 0
        }

    # Initialize topic modeling engine
    engine = TopicModelingEngine(n_topics=10)  # 10 topics to surface nuanced themes

    # Extract topics
    results = engine.extract_topics_from_reviews(reviews, sentiment_filter)

    # Add app context
    results['app_id'] = app_id
    results['app_ids'] = app_ids
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

if __name__ == "__main__":
    import django
    django.setup()
