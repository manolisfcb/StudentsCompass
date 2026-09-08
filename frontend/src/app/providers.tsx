import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { createQueryClient } from "@/app/queryClient";
import "@/i18n";

export function AppProviders({
  children,
  client,
}: {
  children: ReactNode;
  client?: QueryClient;
}) {
  return (
    <QueryClientProvider client={client ?? createQueryClient()}>
      {children}
    </QueryClientProvider>
  );
}
