const DEFAULT_PATTERN = /^[A-Za-z0-9._:-]+$/;

type ValidateIdempotencyKeyOptions = {
  minLength?: number;
  maxLength?: number;
  required?: boolean;
  pattern?: RegExp;
};

export const createIdempotencyKey = (prefix: string): string =>
  `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export const validateIdempotencyKey = (
  value: string,
  options: ValidateIdempotencyKeyOptions = {},
): string | undefined => {
  const {
    minLength = 6,
    maxLength = 64,
    required = true,
    pattern = DEFAULT_PATTERN,
  } = options;

  const trimmed = value.trim();
  if (!trimmed) {
    return required ? 'Idempotency key is required.' : undefined;
  }
  if (trimmed.length < minLength) {
    return `Idempotency key should be at least ${minLength} characters.`;
  }
  if (trimmed.length > maxLength) {
    return `Idempotency key should be at most ${maxLength} characters.`;
  }
  if (!pattern.test(trimmed)) {
    return 'Use only letters, numbers, dot, underscore, colon, or hyphen.';
  }
  return undefined;
};
