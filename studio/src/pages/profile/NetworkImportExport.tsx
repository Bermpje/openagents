/**
 * Network Import/Export page component
 */

import React, { useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import { exportNetwork, validateImport, applyImport } from "@/services/networkManagementService";
import { ImportMode, ImportValidationResult } from "@/types/networkManagement";
import ExportOptionsModal from "@/components/network/ExportOptionsModal";
import ImportPreviewModal from "@/components/network/ImportPreviewModal";
import ImportDropzone from "@/components/network/ImportDropzone";
import { useProfileStore } from "@/stores/profileStore";

const NetworkImportExport: React.FC = () => {
  const { selectedNetwork } = useAuthStore();
  const { refreshData } = useProfileStore();

  // Export state
  const [showExportModal, setShowExportModal] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState(false);

  // Import state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationResult, setValidationResult] = useState<ImportValidationResult | null>(null);
  const [showImportPreview, setShowImportPreview] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importSuccess, setImportSuccess] = useState(false);

  if (!selectedNetwork) {
    return (
      <div className="p-6 dark:bg-gray-900 h-full">
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
          <p className="text-yellow-800 dark:text-yellow-200">
            Please connect to a network first
          </p>
        </div>
      </div>
    );
  }

  // Export handlers
  const handleExportClick = () => {
    setExportError(null);
    setExportSuccess(false);
    setShowExportModal(true);
  };

  const handleExport = async (options: {
    include_password_hashes: boolean;
    include_sensitive_config: boolean;
    notes?: string;
  }) => {
    setIsExporting(true);
    setExportError(null);
    setExportSuccess(false);

    try {
      const blob = await exportNetwork(selectedNetwork!, options);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${selectedNetwork.host}_${selectedNetwork.port}_export_${new Date().toISOString().split("T")[0]}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      setExportSuccess(true);
      setShowExportModal(false);
      setTimeout(() => setExportSuccess(false), 3000);
    } catch (error) {
      console.error("Export failed:", error);
      setExportError(
        error instanceof Error ? error.message : "Export failed, please try again"
      );
    } finally {
      setIsExporting(false);
    }
  };

  // Import handlers
  const handleFileSelected = async (file: File) => {
    setSelectedFile(file);
    setValidationResult(null);
    setImportError(null);
    setImportSuccess(false);
    setIsValidating(true);

    try {
      const result = await validateImport(selectedNetwork!, file);
      setValidationResult(result);
      if (result.valid) {
        setShowImportPreview(true);
      } else {
        setImportError(result.errors.join(", "));
      }
    } catch (error) {
      console.error("Validation failed:", error);
      setImportError(
        error instanceof Error ? error.message : "Validation failed, please try again"
      );
    } finally {
      setIsValidating(false);
    }
  };

  const handleImportConfirm = async (mode: ImportMode, newName?: string) => {
    if (!selectedFile) return;

    setIsImporting(true);
    setImportError(null);
    setImportSuccess(false);

    try {
      const result = await applyImport(selectedNetwork!, selectedFile, mode, newName);

      if (result.success) {
        setImportSuccess(true);
        setShowImportPreview(false);
        setSelectedFile(null);
        setValidationResult(null);

        // Refresh profile data after successful import
        if (result.network_restarted) {
          setTimeout(() => {
            refreshData();
          }, 2000);
        }

        setTimeout(() => setImportSuccess(false), 5000);
      } else {
        setImportError(
          result.errors.length > 0
            ? result.errors.join(", ")
            : result.message || "Import failed"
        );
      }
    } catch (error) {
      console.error("Import failed:", error);
      setImportError(
        error instanceof Error ? error.message : "Import failed, please try again"
      );
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="p-6 dark:bg-gray-900 h-full min-h-screen overflow-y-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Network Import/Export
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Backup, restore, or migrate network configuration
        </p>
      </div>

      {/* Success/Error messages */}
      {exportSuccess && (
        <div className="mb-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
          <p className="text-green-800 dark:text-green-200">
            ✅ Network configuration exported successfully
          </p>
        </div>
      )}

      {exportError && (
        <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-red-800 dark:text-red-200">{exportError}</p>
        </div>
      )}

      {importSuccess && (
        <div className="mb-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
          <p className="text-green-800 dark:text-green-200">
            ✅ Network configuration imported successfully, network is restarting...
          </p>
        </div>
      )}

      {importError && (
        <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-red-800 dark:text-red-200">{importError}</p>
        </div>
      )}

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Export section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Export Network Configuration
            </h2>
            <svg
              className="w-6 h-6 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Export the current network configuration as a .zip file, including network configuration, module configuration, and other information.
          </p>
          <button
            onClick={handleExportClick}
            disabled={isExporting}
            className="w-full inline-flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
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
              "Export Configuration"
            )}
          </button>
        </div>

        {/* Import section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Import Network Configuration
            </h2>
            <svg
              className="w-6 h-6 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Import network configuration from a .zip file. The network will automatically restart after import to apply the new configuration.
          </p>
          <ImportDropzone
            onFileSelected={handleFileSelected}
            disabled={isValidating || isImporting}
          />
          {isValidating && (
            <div className="mt-4 text-sm text-gray-600 dark:text-gray-400 text-center">
              <svg
                className="animate-spin inline-block h-4 w-4 mr-2"
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
              Validating...
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <ExportOptionsModal
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
        onExport={handleExport}
        isExporting={isExporting}
      />

      {validationResult && (
        <ImportPreviewModal
          isOpen={showImportPreview}
          onClose={() => {
            setShowImportPreview(false);
            setSelectedFile(null);
            setValidationResult(null);
          }}
          validationResult={validationResult}
          onConfirm={handleImportConfirm}
          isImporting={isImporting}
        />
      )}
    </div>
  );
};

export default NetworkImportExport;

