// src/ReviewList.jsx
import { useState, useEffect } from 'react';
import axios from 'axios';

function ReviewList() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchReviews = async () => {
      try {
        setLoading(true);
        const response = await axios.get('http://localhost:8000/api/reviews/');
        setReviews(response.data.results || response.data);
        setError(null);
      } catch (err) {
        setError(err.message);
        console.error('Error fetching reviews:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchReviews();
  }, []);

  if (loading) return <div>Loading reviews...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h1>App Reviews ({reviews.length})</h1>
      <div>
        {reviews.map((review) => (
          <div key={review.id} style={{
            border: '1px solid #ccc',
            margin: '10px 0',
            padding: '15px',
            borderRadius: '5px'
          }}>
            <div><strong>Rating:</strong> {review.rating}/5</div>
            <div><strong>Author:</strong> {review.author}</div>
            <div><strong>Content:</strong> {review.content}</div>
            <div><strong>Source:</strong> {review.source}</div>
            <div><strong>Date:</strong> {new Date(review.created_at).toLocaleDateString()}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ReviewList;