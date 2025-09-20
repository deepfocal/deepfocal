import React, { useState } from 'react';
import clsx from 'clsx';
import { useAuth } from './AuthContext';

function LoginForm() {
  const [tab, setTab] = useState('login');
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login, register } = useAuth();

  const handleTabChange = (nextTab) => {
    setTab(nextTab);
    setError('');
    setFormData({ username: '', email: '', password: '' });
  };

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    let result;
    if (tab === 'login') {
      result = await login(formData.username, formData.password);
    } else {
      result = await register(formData.username, formData.email, formData.password);
    }

    if (!result.success) {
      setError(result.error);
    }
    setLoading(false);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-background px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl">
        <div className="text-center">
          <h1 className="text-3xl font-semibold text-gray-base">Deepfocal</h1>
          <p className="mt-2 text-sm text-gray-500">Competitive Intelligence Platform</p>
        </div>

        <div className="mt-6 flex gap-2 rounded-full bg-gray-100 p-1">
          <button
            type="button"
            onClick={() => handleTabChange('login')}
            className={clsx(
              'flex-1 rounded-full px-4 py-2 text-sm font-medium transition-all',
              tab === 'login' ? 'bg-white text-primary shadow' : 'text-gray-500 hover:text-gray-base',
            )}
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('signup')}
            className={clsx(
              'flex-1 rounded-full px-4 py-2 text-sm font-medium transition-all',
              tab === 'signup' ? 'bg-white text-primary shadow' : 'text-gray-500 hover:text-gray-base',
            )}
          >
            Sign Up
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-danger/20 bg-danger/10 px-4 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="username" className="text-sm font-medium text-gray-base">
              Username
            </label>
            <input
              id="username"
              name="username"
              type="text"
              value={formData.username}
              onChange={handleInputChange}
              required
              className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>

          {tab === 'signup' && (
            <div>
              <label htmlFor="email" className="text-sm font-medium text-gray-base">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleInputChange}
                required
                className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>
          )}

          <div>
            <label htmlFor="password" className="text-sm font-medium text-gray-base">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleInputChange}
              required
              className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/70 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {loading ? 'Please wait…' : tab === 'login' ? 'Login' : 'Sign Up'}
          </button>
        </form>

        {tab === 'login' && (
          <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs text-gray-600">
            <p className="font-semibold text-gray-base">Demo Account</p>
            <p className="mt-1">Username: testuser</p>
            <p>Password: testpass123</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default LoginForm;