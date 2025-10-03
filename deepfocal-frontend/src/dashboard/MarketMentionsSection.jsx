import React, { useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';
import { Pagination, Typography } from '@mui/material';
import { ChevronDown, ExternalLink, Globe, MessageCircle } from 'lucide-react';
import apiClient from '../apiClient';

const SOURCE_STYLES = {
  Reddit: {
    badge: 'bg-blue-100 text-blue-700',
    icon: MessageCircle,
  },
  'Web Search': {
    badge: 'bg-teal-100 text-teal-700',
    icon: Globe,
  },
};

const SENTIMENT_STYLES = {
  positive: {
    border: 'border-emerald-500',
    text: 'text-emerald-600',
    label: 'Positive',
  },
  neutral: {
    border: 'border-gray-300',
    text: 'text-gray-600',
    label: 'Neutral',
  },
  negative: {
    border: 'border-rose-500',
    text: 'text-rose-600',
    label: 'Negative',
  },
};

const formatSentiment = (value) => {
  const numeric = typeof value === 'number' ? value : Number(value || 0);
  if (Number.isNaN(numeric)) {
    return SENTIMENT_STYLES.neutral;
  }
  if (numeric > 0.2) {
    return SENTIMENT_STYLES.positive;
  }
  if (numeric < -0.2) {
    return SENTIMENT_STYLES.negative;
  }
  return SENTIMENT_STYLES.neutral;
};

const formatTimestamp = (value) => {
  if (!value) {
    return 'Unknown date';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Unknown date';
  }

  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

function MarketMentionCard({ mention, isExpanded, onToggle }) {
  const sentiment = formatSentiment(mention.sentiment_score);
  const sourceStyle = SOURCE_STYLES[mention.source] || {
    badge: 'bg-gray-100 text-gray-600',
    icon: Globe,
  };
  const SourceIcon = sourceStyle.icon;
  const preview = mention.content?.length > 150
    ? `${mention.content.slice(0, 150)}…`
    : mention.content || 'No preview available.';

  return (
    <div
      className={clsx(
        'overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-all',
        'border-l-4',
        sentiment.border,
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full px-5 py-4 text-left"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={clsx(
                  'inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide',
                  sourceStyle.badge,
                )}
              >
                <SourceIcon className="h-3.5 w-3.5" />
                {mention.source || 'Unknown Source'}
              </span>
              <span className={clsx('text-xs font-semibold uppercase tracking-wide', sentiment.text)}>
                {sentiment.label}
              </span>
              {typeof mention.sentiment_score === 'number' && (
                <span className="text-xs font-medium text-gray-400">
                  {mention.sentiment_score.toFixed(2)}
                </span>
              )}
            </div>
            {mention.title && (
              <p className="text-sm font-semibold text-gray-900 line-clamp-2">{mention.title}</p>
            )}
            <p className="text-sm leading-relaxed text-gray-700 line-clamp-3">{preview}</p>
          </div>
          <ChevronDown
            className={clsx(
              'mt-1 h-5 w-5 flex-shrink-0 text-gray-400 transition-transform',
              isExpanded && 'rotate-180 text-gray-500',
            )}
          />
        </div>
      </button>
      {isExpanded && (
        <div className="border-t border-gray-100 bg-gray-50 px-5 py-4 text-sm text-gray-700">
          <p className="whitespace-pre-line leading-relaxed text-gray-800">{mention.content}</p>
          <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-gray-500">
            <span>{formatTimestamp(mention.created_at)}</span>
            {mention.url && (
              <a
                href={mention.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-medium text-primary hover:text-primary/80"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                View Source
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function MarketMentionsSection({ appId }) {
  const [mentions, setMentions] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeSource, setActiveSource] = useState('All');
  const [expandedIndex, setExpandedIndex] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(10);

  useEffect(() => {
    setActiveSource('All');
    setExpandedIndex(null);

    if (!appId) {
      setMentions([]);
      setTotalCount(0);
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError('');

    apiClient
      .get('/api/market-mentions/', {
        params: { app_id: appId },
      })
      .then((response) => {
        if (!isMounted) {
          return;
        }
        const data = response?.data ?? {};
        const list = Array.isArray(data.market_mentions) ? data.market_mentions : [];
        setMentions(list);
        if (typeof data.total_count === 'number') {
          setTotalCount(data.total_count);
        } else {
          setTotalCount(list.length);
        }
      })
      .catch((err) => {
        if (!isMounted) {
          return;
        }
        const message = err?.response?.data?.error || err?.message || 'Unable to load market mentions.';
        setError(message);
        setMentions([]);
        setTotalCount(0);
      })
      .finally(() => {
        if (isMounted) {
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [appId]);

  useEffect(() => {
    setExpandedIndex(null);
    setCurrentPage(1);
  }, [mentions, activeSource]);

  const availableSources = useMemo(() => {
    const uniqueSources = Array.from(new Set(mentions.map((item) => item.source).filter(Boolean)));
    return ['All', ...uniqueSources];
  }, [mentions]);

  const filteredMentions = useMemo(() => {
    if (activeSource === 'All') {
      return mentions;
    }
    return mentions.filter((item) => item.source === activeSource);
  }, [activeSource, mentions]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(filteredMentions.length / itemsPerPage) || 1);
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [filteredMentions, currentPage, itemsPerPage]);

  const total = filteredMentions.length;
  const totalPages = Math.max(1, Math.ceil(total / itemsPerPage) || 1);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const displayedMentions = filteredMentions.slice(startIndex, endIndex);
  const startDisplay = total === 0 ? 0 : startIndex + 1;
  const endDisplay = total === 0 ? 0 : Math.min(endIndex, total);

  if (!appId) {
    return null;
  }

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-base">Market Mentions</h3>
          <p className="text-sm text-gray-500">Voice-of-the-market signals spanning Reddit, the web, and more.</p>
        </div>
        <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-700">
          {totalCount} mentions
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {availableSources.map((source) => (
          <button
            key={source}
            type="button"
            onClick={() => setActiveSource(source)}
            className={clsx(
              'rounded-full border px-3 py-1 text-xs font-semibold transition-colors',
              activeSource === source
                ? 'border-gray-900 bg-gray-900 text-white'
                : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300',
            )}
          >
            {source}
          </button>
        ))}
      </div>

      <div className="mt-6 space-y-4">
        {loading && <p className="text-sm text-gray-500">Loading market mentions…</p>}
        {!loading && error && (
          <p className="text-sm text-danger">{error}</p>
        )}
        {!loading && !error && total === 0 && (
          <p className="text-sm text-gray-500">No market mentions found for this app yet.</p>
        )}
        {!loading && !error && displayedMentions.map((mention, index) => (
          <MarketMentionCard
            key={mention.url || `${mention.source}-${startIndex + index}`}
            mention={mention}
            isExpanded={expandedIndex === startIndex + index}
            onToggle={() =>
              setExpandedIndex((prev) => (prev === startIndex + index ? null : startIndex + index))
            }
          />
        ))}
      </div>

      {!loading && !error && total > 0 && (
        <div className="mt-6 flex flex-col items-center gap-3">
          <Typography variant="body2" color="text.secondary">
            Showing {startDisplay}-{endDisplay} of {total} mentions
          </Typography>
          {totalPages > 1 && (
            <Pagination
              count={totalPages}
              page={currentPage}
              onChange={(event, page) => setCurrentPage(page)}
              color="primary"
              siblingCount={1}
              boundaryCount={1}
            />
          )}
        </div>
      )}
    </section>
  );
}
