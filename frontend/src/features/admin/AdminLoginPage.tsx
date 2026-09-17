import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { PageScope } from "@/components/layout/PageScope";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
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

  const message = mutation.error instanceof ApiError && mutation.error.status === 403
    ? t("admin.login.notAdmin")
    : t("admin.login.invalid");

  return (
    <PageScope name={["admin", "admin-page"]} className="admin-login-page">
      <DocumentMeta title={t("admin.login.seoTitle")} description={t("admin.login.subtitle")} path="/admin/login" />
      <main className="admin-login-card">
        <div className="admin-login-header">
          <div className="admin-login-icon" aria-hidden="true">
            🛡️
          </div>
          <h1 className="admin-login-title">{t("admin.login.title")}</h1>
          <p className="admin-login-subtitle">{t("admin.login.subtitle")}</p>
        </div>

        {mutation.isError ? (
          <div className="admin-login-error visible" role="alert">
            {message}
          </div>
        ) : null}

        <form onSubmit={submit}>
          <div className="admin-form-group">
            <label className="admin-form-label" htmlFor="adminEmail">
              {t("admin.login.email")}
            </label>
            <input
              className="admin-form-input"
              id="adminEmail"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="admin-form-group">
            <label className="admin-form-label" htmlFor="adminPassword">
              {t("admin.login.password")}
            </label>
            <input
              className="admin-form-input"
              id="adminPassword"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <button type="submit" className="admin-login-btn" disabled={mutation.isPending}>
            {mutation.isPending ? t("admin.login.submitting") : t("admin.login.submit")}
          </button>
        </form>

        <Link to="/" className="admin-login-subtitle">
          {t("admin.backToSite")}
        </Link>
      </main>
    </PageScope>
  );
}
