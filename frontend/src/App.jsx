// file: frontend/src/App.jsx

import { useState, useEffect } from 'react';
import './App.css'; // We'll use this for some basic styling

function App() {
  // 'useState' is a React Hook to manage the state of our component
  const [reviews, setReviews] = useState([]); // A place to store the reviews we fetch
  const [error, setError] = useState(null);   // A place to store any errors

  // 'useEffect' is a React Hook that runs code after the component renders.
  // We use it to fetch our data.
  useEffect(() => {
    const apiUrl = 'http://127.0.0.1:8000/api/reviews/';

    async function fetchReviews() {
      try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
          throw new Error(`Network response was not ok. Status: ${response.status}`);
        }
        const data = await response.json();
        setReviews(data); // Save the fetched data into our state
      } catch (error) {
        console.error("Failed to fetch reviews:", error);
        setError(error.message); // Save the error message
      }
    }

    fetchReviews();
  }, []); // The empty array [] means this effect runs only once when the component mounts

  return (
    <div className="App">
      <header className="App-header">
        <h1>Deepfocal - Data View</h1>
        <p>This page is fetching data live from your Django API.</p>
      </header>
      <main>
        {/* Conditional Rendering: Show an error, a loading message, or the table */}
        {error ? (
          <p className="error-message">Failed to load data: {error}</p>
        ) : reviews.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Author</th>
                <th>Rating</th>
                <th>Title</th>
                <th>Sentiment</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((review) => (
                // We use a unique 'key' for each item in a list for React to keep track
                <tr key={review.id}>
                  <td>{review.source}</td>
                  <td>{review.author}</td>
                  <td>{review.rating}</td>
                  <td>{review.title}</td>
                  <td>{review.sentiment_label}</td>
                  <td>{review.sentiment_score ? review.sentiment_score.toFixed(4) : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>Loading reviews...</p>
        )}
      </main>
    </div>
  );
}

export default App;