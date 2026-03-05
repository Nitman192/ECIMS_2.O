import axios from 'axios';

const coerceMessage = (value: unknown): string | null => {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }

  if (Array.isArray(value)) {
    const joined = value
      .map((item) => coerceMessage(item))
      .filter((item): item is string => Boolean(item))
      .join(', ');
    return joined || null;
  }

  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (record.msg) return coerceMessage(record.msg);
    if (record.message) return coerceMessage(record.message);
    if (record.detail) return coerceMessage(record.detail);
  }

  return null;
};

export const getApiErrorMessage = (error: unknown, fallback = 'Request failed'): string => {
  if (axios.isAxiosError(error)) {
    const responseMessage =
      coerceMessage(error.response?.data) ||
      coerceMessage((error.response?.data as Record<string, unknown> | undefined)?.detail);
    if (responseMessage) return responseMessage;
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }

  return fallback;
};

export const normalizeListResponse = <T,>(payload: unknown): T[] => {
  if (Array.isArray(payload)) return payload as T[];
  if (!payload || typeof payload !== 'object') return [];

  const record = payload as Record<string, unknown>;
  const keys = ['items', 'results', 'data'] as const;
  for (const key of keys) {
    if (Array.isArray(record[key])) return record[key] as T[];
  }

  return [];
};
