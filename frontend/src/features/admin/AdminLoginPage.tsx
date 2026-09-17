import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Alert, Button, Card, FormField, Input } from "@/components/ui";
import { fetchAdminStats } from "@/features/admin/api";
import { login } from "@/features/auth/api";

export function AdminLoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: async () => {
      await login("student", { email, password });
      // The login endpoint authenticates students in general. This API call
      // is the authorization check; only the backend decides who is admin.
      await fetchAdminStats();
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.session.current });
      navigate("/admin", { replace: true });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.reset();
    mutation.mutate();
  }

  const message =
    mutation.error instanceof ApiError && mutation.error.status === 403
      ? t("admin.login.notAdmin")
      : t("admin.login.invalid");

  return (
    // `theme-dark` is the console's whole theme: the same tokens, re-pointed.
    // The card below is the design system's `Card`, with no dark-specific
    // class on it — and the layout is centred, which the ported sheet never
    // managed (it pinned the card to the top-left corner).
    <div className="theme-dark flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <DocumentMeta title={t("admin.login.seoTitle")} description={t("admin.login.subtitle")} path="/admin/login" />

      <main className="w-full max-w-sm">
        <Card padding="lg" className="flex flex-col gap-5">
          <div className="text-center">
            <div
              aria-hidden="true"
              className="mx-auto mb-3 flex size-12 items-center justify-center rounded-xl bg-primary text-2xl"
            >
              🛡️
            </div>
            <h1 className="text-section-title text-ink">{t("admin.login.title")}</h1>
            <p className="mt-1 text-body-sm text-ink-soft">{t("admin.login.subtitle")}</p>
          </div>

          {mutation.isError ? <Alert tone="danger">{message}</Alert> : null}

          <form onSubmit={submit} className="flex flex-col gap-4">
            <FormField label={t("admin.login.email")}>
              <Input
                id="adminEmail"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </FormField>

            <FormField label={t("admin.login.password")}>
              <Input
                id="adminPassword"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </FormField>

            <Button type="submit" size="lg" block loading={mutation.isPending}>
              {mutation.isPending ? t("admin.login.submitting") : t("admin.login.submit")}
            </Button>
          </form>

          <Link
            to="/"
            className="text-center text-body-sm text-ink-muted transition-colors hover:text-ink"
          >
            {t("admin.backToSite")}
          </Link>
        </Card>
      </main>
    </div>
  );
}
