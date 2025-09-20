// src/components/LoadingOverlay.jsx - Fixed version
import React from 'react';
import { useTask } from '../contexts/TaskContext';

const LoadingOverlay = ({ appId }) => {
  const { getTaskStatus } = useTask();
  const taskStatus = getTaskStatus(appId);

  if (!taskStatus) return null;

  const progressPercentage = taskStatus.progress || 0;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4 shadow-xl">
        <div className="text-center">
          {/* Spinner */}
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600 mx-auto mb-4"></div>

          {/* Title */}
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Analyzing Reviews
          </h3>

          {/* Status message */}
          <p className="text-sm text-gray-600 mb-4">
            {taskStatus.step}
          </p>

          {/* Progress bar */}
          <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
            <div
              className="bg-teal-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progressPercentage}%` }}
            ></div>
          </div>

          {/* Progress text */}
          <p className="text-xs text-gray-500 mb-2">
            {progressPercentage}% complete
          </p>

          {/* Review count if available */}
          {taskStatus.currentReviews && (
            <p className="text-xs text-gray-400">
              {taskStatus.currentReviews} / {taskStatus.totalReviews} reviews processed
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default LoadingOverlay;