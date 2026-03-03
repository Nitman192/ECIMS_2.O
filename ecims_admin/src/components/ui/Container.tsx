// src/components/ui/Container.tsx
import type { ReactNode } from 'react';

type ContainerProps = {
  children: ReactNode;
  className?: string;
};

export const Container = ({ children, className = '' }: ContainerProps) => {
  return <div className={`mx-auto w-full max-w-7xl ${className}`}>{children}</div>;
};
