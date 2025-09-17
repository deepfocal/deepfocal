# Deepfocal: AI-Powered Competitive Intelligence Platform

## What Deepfocal Does

Deepfocal transforms app store reviews into actionable business intelligence in under 10 minutes. Instead of manually reading thousands of competitor reviews, Deepfocal's AI automatically extracts the insights that drive product decisions, competitive strategy, and customer retention.

---

## The Problem

Product and marketing teams are flying blind. They are overwhelmed by the massive volume of unstructured customer feedback scattered across the web. This leads to:
*   **Wasted Hours:** Manually reading and categorizing thousands of reviews is slow, biased, and inefficient.
*   **Reactive Strategy:** Teams are forced to react to competitive threats only after they've already lost customers.
*   **High-Risk Decisions:** Roadmap priorities are often based on gut feelings or anecdotal evidence, not real market data.

---

## The Solution

Deepfocal is an on-demand, competitive intelligence platform that provides:

*   **Competitive Sentiment Benchmarking:** Instantly see how your app's sentiment compares to any competitor.
*   **AI-Discovered Pain Points:** Automatically discover the top themes and pain points from negative reviews using LDA Topic Modeling.
*   **Strategic Business Intelligence:** Go beyond raw data with calculated scores for **Churn Risk**, **Competitive Gaps**, and **Pricing Risk**.

---

## Technology Differentiators

*   **Advanced AI Pipeline:** We use a review-specific BERT model for sentiment analysis and LDA for topic modeling to discover themes automatically from raw user language.
*   **Speed-to-Insight Focus:** Our architecture is designed to deliver real-time analysis of competitor apps, generating a complete intelligence dashboard in minutes, not hours.
*   **True Market Intelligence:** By focusing on public reviews, we analyze the "voice of the market"—including prospects and your competitors' customers—providing an unbiased view that internal feedback tools cannot.

---

## Project Status

This repository contains the source code for the Deepfocal MVP.

*   **Backend:** Django REST Framework with a PostgreSQL database.
*   **AI Engine:** Uses Hugging Face Transformers for sentiment and Scikit-learn for topic modeling. Asynchronous tasks are managed by Celery with Redis.
*   **Frontend:** A modern, interactive dashboard built with React and Vite.

The current prototype has a working end-to-end data pipeline: it can ingest reviews from the Apple App Store and Google Play Store, perform sentiment analysis, and display the results via an API to a simple frontend. The next phase of development is to build out the interactive, user-driven dashboard.