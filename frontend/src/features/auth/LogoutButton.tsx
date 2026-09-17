import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { type ActorKind, logout } from "@/features/auth/api";
import { cn } from "@/lib/cn";

/**
 * One shell, one identity. A person can hold a student cookie and a recruiter
 * cookie at once (`guards.tsx`), so logging out is scoped to the actor the
 * current shell represents rather than clearing every session the browser
 * holds.
 */
export function LogoutButton({
  actorKind,
  className,
}: {
  actorKind: ActorKind;
  /**
   * Overrides the default treatment. The default suits a coloured header bar;
   * the admin console passes nothing and inherits it too, because its header
   * is a dark surface where the same translucent-white fill still reads.
   */
  className?: string;
}) {
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
    <button
      type="button"
      className={cn(
        "flex h-9 items-center justify-center rounded-md border border-white/25 px-3 text-body-sm font-medium text-white transition-colors",
        "hover:bg-white/10 disabled:pointer-events-none disabled:opacity-60",
        className,
      )}
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
    >
      {mutation.isPending ? t("auth.logout.pending") : t("auth.logout.label")}
    </button>
  );
}
