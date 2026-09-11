import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchAdminStats } from "@/features/admin/api";
import { login } from "@/features/auth/api";
import { Field, INPUT_CLASS } from "@/features/auth/formParts";

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

  const message = mutation.error instanceof ApiError && mutation.error.status === 403
    ? t("admin.login.notAdmin")
    : t("admin.login.invalid");

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink px-4 py-10">
      <DocumentMeta title={t("admin.login.seoTitle")} description={t("admin.login.subtitle")} path="/admin/login" />
      <main className="w-full max-w-md rounded-xl border border-white/10 bg-white p-7 shadow-xl">
        <div className="text-center">
          <span aria-hidden="true" className="text-4xl">🛡️</span>
          <h1 className="mt-3 text-2xl font-bold text-ink">{t("admin.login.title")}</h1>
          <p className="mt-1 text-sm text-ink-soft">{t("admin.login.subtitle")}</p>
        </div>
        {mutation.isError ? <div className="mt-5"><Alert tone="danger">{message}</Alert></div> : null}
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <Field label={t("admin.login.email")}>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field label={t("admin.login.password")}>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? t("admin.login.submitting") : t("admin.login.submit")}
          </Button>
        </form>
        <Link to="/" className="mt-5 block text-center text-sm text-ink-soft hover:text-brand">
          {t("admin.backToSite")}
        </Link>
      </main>
    </div>
  );
}
