/**
 * Import preview and confirmation modal component
 */

import React, { useState } from "react";
import { ImportMode, ImportValidationResult } from "@/types/networkManagement";

interface ImportPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  validationResult: ImportValidationResult;
  onConfirm: (mode: ImportMode, newName?: string) => void;
  isImporting?: boolean;
}

const ImportPreviewModal: React.FC<ImportPreviewModalProps> = ({
  isOpen,
  onClose,
  validationResult,
  onConfirm,
  isImporting = false,
}) => {
  const [importMode, setImportMode] = useState<ImportMode>(ImportMode.OVERWRITE);
  const [newName, setNewName] = useState("");

  if (!isOpen) return null;

  const { manifest, preview, warnings, errors } = validationResult;

  const handleConfirm = () => {
    if (importMode === ImportMode.CREATE_NEW && !newName.trim()) {
      return; // Validation handled by UI
    }
    onConfirm(importMode, newName.trim() || undefined);
  };

  const handleClose = () => {
    if (!isImporting) {
      setImportMode(ImportMode.OVERWRITE);
      setNewName("");
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
        <div className="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full">
          <div className="px-4 pt-5 pb-4 sm:p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-gray-100">
                Import Preview
              </h3>
              {!isImporting && (
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
              {/* Manifest info */}
              {manifest && (
                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">
                    Export Information
                  </h4>
                  <dl className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <dt className="text-gray-500 dark:text-gray-400">Network Name</dt>
                      <dd className="text-gray-900 dark:text-gray-100">
                        {manifest.network_name}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-gray-400">Export Time</dt>
                      <dd className="text-gray-900 dark:text-gray-100">
                        {new Date(manifest.export_timestamp).toLocaleString()}
                      </dd>
                    </div>
                    {manifest.openagents_version && (
                      <div>
                        <dt className="text-gray-500 dark:text-gray-400">Version</dt>
                        <dd className="text-gray-900 dark:text-gray-100">
                          {manifest.openagents_version}
                        </dd>
                      </div>
                    )}
                    <div>
                      <dt className="text-gray-500 dark:text-gray-400">Modules Count</dt>
                      <dd className="text-gray-900 dark:text-gray-100">
                        {manifest.mods_count}
                      </dd>
                    </div>
                  </dl>
                  {manifest.notes && (
                    <div className="mt-2">
                      <dt className="text-sm text-gray-500 dark:text-gray-400">Notes</dt>
                      <dd className="text-sm text-gray-900 dark:text-gray-100 mt-1">
                        {manifest.notes}
                      </dd>
                    </div>
                  )}
                </div>
              )}

              {/* Preview info */}
              {preview && (
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">
                    Content to Import
                  </h4>
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-2 text-sm">
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Network Name: </span>
                      <span className="text-gray-900 dark:text-gray-100">
                        {preview.network_name}
                      </span>
                    </div>
                    {preview.mods_to_add.length > 0 && (
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Modules to Add: </span>
                        <span className="text-gray-900 dark:text-gray-100">
                          {preview.mods_to_add.join(", ")}
                        </span>
                      </div>
                    )}
                    {preview.mods_to_update.length > 0 && (
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Modules to Update: </span>
                        <span className="text-gray-900 dark:text-gray-100">
                          {preview.mods_to_update.join(", ")}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Warnings */}
              {warnings.length > 0 && (
                <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
                  <h4 className="text-sm font-medium text-yellow-800 dark:text-yellow-200 mb-2">
                    Warnings
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700 dark:text-yellow-300">
                    {warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Errors */}
              {errors.length > 0 && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                  <h4 className="text-sm font-medium text-red-800 dark:text-red-200 mb-2">
                    Errors
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-red-700 dark:text-red-300">
                    {errors.map((error, index) => (
                      <li key={index}>{error}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Import mode selection */}
              {validationResult.valid && (
                <div className="space-y-3">
                  <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    Import Mode
                  </h4>
                  <div className="space-y-2">
                    <label className="flex items-center">
                      <input
                        type="radio"
                        value={ImportMode.OVERWRITE}
                        checked={importMode === ImportMode.OVERWRITE}
                        onChange={(e) => setImportMode(e.target.value as ImportMode)}
                        disabled={isImporting}
                        className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                      />
                      <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                        Overwrite Existing Configuration (will replace current network configuration)
                      </span>
                    </label>
                    <label className="flex items-center">
                      <input
                        type="radio"
                        value={ImportMode.CREATE_NEW}
                        checked={importMode === ImportMode.CREATE_NEW}
                        onChange={(e) => setImportMode(e.target.value as ImportMode)}
                        disabled={isImporting}
                        className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                      />
                      <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                        Create New Network (requires new name)
                      </span>
                    </label>
                  </div>

                  {/* New name input for CREATE_NEW mode */}
                  {importMode === ImportMode.CREATE_NEW && (
                    <div>
                      <label
                        htmlFor="new-network-name"
                        className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                      >
                        New Network Name
                      </label>
                      <input
                        id="new-network-name"
                        type="text"
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        disabled={isImporting}
                        placeholder="Enter new network name"
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Footer buttons */}
          <div className="px-4 py-3 bg-gray-50 dark:bg-gray-700 sm:px-6 sm:flex sm:flex-row-reverse">
            {validationResult.valid && (
              <button
                onClick={handleConfirm}
                disabled={
                  isImporting ||
                  (importMode === ImportMode.CREATE_NEW && !newName.trim())
                }
                className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isImporting ? (
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
                    Importing...
                  </>
                ) : (
                  "Confirm Import"
                )}
              </button>
            )}
            <button
              onClick={handleClose}
              disabled={isImporting}
              className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 dark:border-gray-600 shadow-sm px-4 py-2 bg-white dark:bg-gray-800 text-base font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {validationResult.valid ? "Cancel" : "Close"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImportPreviewModal;

