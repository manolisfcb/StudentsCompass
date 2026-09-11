import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { Button } from "@/components/primitives/Button";
import { type ActorKind, logout } from "@/features/auth/api";

/**
 * One shell, one identity. A person can hold a student cookie and a recruiter
 * cookie at once (`guards.tsx`), so logging out is scoped to the actor the
 * current shell represents rather than clearing every session the browser
 * holds.
 */
export function LogoutButton({ actorKind, className }: { actorKind: ActorKind; className?: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => logout(actorKind),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.session.current });
      navigate("/", { replace: true });
    },
  });

  return (
    <Button variant="ghost" className={className} onClick={() => mutation.mutate()} disabled={mutation.isPending}>
      {mutation.isPending ? t("auth.logout.pending") : t("auth.logout.label")}
    </Button>
  );
}
