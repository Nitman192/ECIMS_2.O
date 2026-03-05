export const toOptionalQuery = (value: string): string | undefined => {
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
};

export const toOptionalFilter = (value: string, allValue = 'all'): string | undefined => {
  return value !== allValue ? value : undefined;
};
