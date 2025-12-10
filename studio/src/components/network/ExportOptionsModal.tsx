/**
 * Export options modal component
 */

import React, { useState } from "react";

interface ExportOptionsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onExport: (options: {
    include_password_hashes: boolean;
    include_sensitive_config: boolean;
    notes?: string;
  }) => void;
  isExporting?: boolean;
}

const ExportOptionsModal: React.FC<ExportOptionsModalProps> = ({
  isOpen,
  onClose,
  onExport,
  isExporting = false,
}) => {
  const [includePasswordHashes, setIncludePasswordHashes] = useState(false);
  const [includeSensitiveConfig, setIncludeSensitiveConfig] = useState(false);
  const [notes, setNotes] = useState("");

  if (!isOpen) return null;

  const handleExport = () => {
    onExport({
      include_password_hashes: includePasswordHashes,
      include_sensitive_config: includeSensitiveConfig,
      notes: notes.trim() || undefined,
    });
  };

  const handleClose = () => {
    if (!isExporting) {
      setIncludePasswordHashes(false);
      setIncludeSensitiveConfig(false);
      setNotes("");
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        {/* Background overlay */}
        <div
          className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75 dark:bg-gray-900 dark:bg-opacity-75"
          onClick={handleClose}
        />

        {/* Modal panel */}
        <div className="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
          <div className="px-4 pt-5 pb-4 sm:p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-gray-100">
                Export Network Configuration
              </h3>
              {!isExporting && (
                <button
                  onClick={handleClose}
                  className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
                >
                  <svg
                    className="w-6 h-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              )}
            </div>

            <div className="space-y-4">
              {/* Password hashes option */}
              <div className="flex items-start">
                <div className="flex items-center h-5">
                  <input
                    id="include-password-hashes"
                    type="checkbox"
                    checked={includePasswordHashes}
                    onChange={(e) => setIncludePasswordHashes(e.target.checked)}
                    disabled={isExporting}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                  />
                </div>
                <div className="ml-3 text-sm">
                  <label
                    htmlFor="include-password-hashes"
                    className="font-medium text-gray-700 dark:text-gray-300"
                  >
                    Include Password Hashes
                  </label>
                  <p className="text-gray-500 dark:text-gray-400">
                    Export agent group password hashes (for restoring complete configuration)
                  </p>
                </div>
              </div>

              {/* Sensitive config option */}
              <div className="flex items-start">
                <div className="flex items-center h-5">
                  <input
                    id="include-sensitive-config"
                    type="checkbox"
                    checked={includeSensitiveConfig}
                    onChange={(e) => setIncludeSensitiveConfig(e.target.checked)}
                    disabled={isExporting}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                  />
                </div>
                <div className="ml-3 text-sm">
                  <label
                    htmlFor="include-sensitive-config"
                    className="font-medium text-gray-700 dark:text-gray-300"
                  >
                    Include Sensitive Configuration
                  </label>
                  <p className="text-gray-500 dark:text-gray-400">
                    Export sensitive information such as API keys and tokens
                  </p>
                </div>
              </div>

              {/* Notes */}
              <div>
                <label
                  htmlFor="export-notes"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                >
                  Notes (Optional)
                </label>
                <textarea
                  id="export-notes"
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  disabled={isExporting}
                  placeholder="Add notes about this export..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                />
              </div>
            </div>
          </div>

          {/* Footer buttons */}
          <div className="px-4 py-3 bg-gray-50 dark:bg-gray-700 sm:px-6 sm:flex sm:flex-row-reverse">
            <button
              onClick={handleExport}
              disabled={isExporting}
              className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isExporting ? (
                <>
                  <svg
                    className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Exporting...
                </>
              ) : (
                "Export"
              )}
            </button>
            <button
              onClick={handleClose}
              disabled={isExporting}
              className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 dark:border-gray-600 shadow-sm px-4 py-2 bg-white dark:bg-gray-800 text-base font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExportOptionsModal;

