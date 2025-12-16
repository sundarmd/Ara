/**
 * Centralized application constants
 * Single source of truth for API configuration and business constants
 */

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const BANKS = ['GS', 'JPM', 'UBS', 'MS', 'BARC', 'CITI'] as const;
export const ASSET_CLASSES = ['equity', 'fixed_income', 'multi_asset', 'fx', 'rates', 'credit'] as const;

// TypeScript type helpers for strict typing
export type Bank = typeof BANKS[number];
export type AssetClass = typeof ASSET_CLASSES[number];
