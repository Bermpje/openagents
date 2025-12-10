/**
 * Network management service for import/export operations
 */

import { networkFetch } from "@/utils/httpClient";
import { NetworkConnection } from "@/types/connection";
import {
  ImportMode,
  ImportValidationResult,
  ImportResult,
  ExportOptions,
} from "@/types/networkManagement";

/**
 * Export network configuration as ZIP file
 */
export const exportNetwork = async (
  connection: NetworkConnection,
  options: ExportOptions
): Promise<Blob> => {
  const params = new URLSearchParams();
  if (options.include_password_hashes) {
    params.append("include_password_hashes", "true");
  }
  if (options.include_sensitive_config) {
    params.append("include_sensitive_config", "true");
  }
  if (options.notes) {
    params.append("notes", options.notes);
  }

  const queryString = params.toString();
  const endpoint = `/api/network/export${queryString ? `?${queryString}` : ""}`;

  const response = await networkFetch(
    connection.host,
    connection.port,
    endpoint,
    {
      method: "GET",
      useHttps: connection.useHttps || false,
    }
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Export failed: ${response.status} ${errorText}`);
  }

  return await response.blob();
};

/**
 * Validate import file before applying
 */
export const validateImport = async (
  connection: NetworkConnection,
  file: File
): Promise<ImportValidationResult> => {
  const formData = new FormData();
  formData.append("file", file);

  // Use direct fetch for FormData to avoid Content-Type header issues
  const protocol = connection.useHttps ? "https" : "http";
  const url = `${protocol}://${connection.host}:${connection.port}/api/network/import/validate`;

  const response = await fetch(url, {
    method: "POST",
    body: formData,
    // Don't set Content-Type header, let browser set it with boundary for FormData
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Validation failed: ${response.status} ${errorText}`);
  }

  return await response.json();
};

/**
 * Apply imported network configuration
 */
export const applyImport = async (
  connection: NetworkConnection,
  file: File,
  mode: ImportMode,
  newName?: string
): Promise<ImportResult> => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mode", mode);
  if (newName) {
    formData.append("new_name", newName);
  }

  // Use direct fetch for FormData to avoid Content-Type header issues
  const protocol = connection.useHttps ? "https" : "http";
  const url = `${protocol}://${connection.host}:${connection.port}/api/network/import/apply`;

  const response = await fetch(url, {
    method: "POST",
    body: formData,
    // Don't set Content-Type header, let browser set it with boundary for FormData
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Import failed: ${response.status} ${errorText}`);
  }

  return await response.json();
};

