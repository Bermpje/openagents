/**
 * Type definitions for network import/export functionality
 */

export enum ImportMode {
  CREATE_NEW = "create_new",
  OVERWRITE = "overwrite",
  MERGE = "merge",
}

export interface ExportManifest {
  export_version: string;
  network_name: string;
  export_timestamp: string;
  openagents_version?: string;
  notes?: string;
  includes_password_hashes: boolean;
  includes_sensitive_config: boolean;
  mods_count: number;
  has_network_profile: boolean;
}

export interface ImportPreview {
  network_name: string;
  mode: ImportMode;
  mods_to_add: string[];
  mods_to_update: string[];
  has_network_profile: boolean;
  config_changes: Record<string, any>;
}

export interface ImportValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  manifest?: ExportManifest;
  preview?: ImportPreview;
}

export interface ImportResult {
  success: boolean;
  message: string;
  errors: string[];
  warnings: string[];
  network_restarted: boolean;
  applied_config?: {
    network_name: string;
    mode: string;
    mods_count: number;
  };
}

export interface ExportOptions {
  include_password_hashes: boolean;
  include_sensitive_config: boolean;
  notes?: string;
}

