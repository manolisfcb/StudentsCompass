import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { homePathFor } from "@/app/routes";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { type ActorKind, describeAuthError, login } from "@/features/auth/api";
import { AccountTypeToggle, AsidePoint, Field } from "@/features/auth/formParts";

/** Where `RequireActor` sends an anonymous visitor it just bounced. */
interface LocationState {
  from?: { pathname: string };
}

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const [kind, setKind] = useState<ActorKind>("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: () => login(kind, { email, password }),
    onSuccess: async () => {
      // The cookie just changed identity; a stale cached "anonymous" would
      // send the person right back through `RequireAnonymous`.
      await queryClient.invalidateQueries({ queryKey: queryKeys.session.current });
      const state = location.state as LocationState | null;
      navigate(state?.from?.pathname ?? homePathFor(kind === "company" ? "recruiter" : "student"), {
        replace: true,
      });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.reset();
    mutation.mutate();
  }

  return (
    <div className="auth-container">
      <DocumentMeta title={t("auth.login.title")} description={t("auth.login.seoDescription")} path="/login" />

      <div className="auth-shell">
        <aside className="auth-aside">
          <Link to="/" className="auth-brand" aria-label={t("app.name")}>
            <img src="/images/Logo_Ready_to_Use.png" alt={t("layout.logoAlt")} className="brand-logo brand-logo--hero" />
          </Link>
          <span className="auth-kicker">{t("auth.login.kicker")}</span>
          <h1>{t("auth.login.heroTitle")}</h1>
          <p>{t("auth.login.heroBody")}</p>
          <div className="auth-aside-points">
            <AsidePoint icon="🧭" title={t("auth.login.point1.title")} body={t("auth.login.point1.body")} />
            <AsidePoint icon="⚡" title={t("auth.login.point2.title")} body={t("auth.login.point2.body")} />
          </div>
        </aside>

        <div className="auth-card">
          <div className="auth-form-header">
            <Link to="/" className="auth-back-link">
              {t("auth.backToHome")}
            </Link>
            <h2>{t("auth.login.title")}</h2>
            <p>{t("auth.login.subtitle")}</p>
          </div>

          {mutation.isError ? (
            <div className="auth-message auth-message-error is-visible" role="alert">
              {describeAuthError(mutation.error, t)}
            </div>
          ) : null}

          <form onSubmit={handleSubmit} noValidate>
            <AccountTypeToggle idPrefix="type" name="login-type" value={kind} onChange={setKind} />

            <Field label={t("auth.login.email")} htmlFor="login-email">
              <input
                id="login-email"
                type="email"
                required
                autoComplete="email"
                placeholder={t("auth.login.emailPlaceholder")}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>

            <Field label={t("auth.login.password")} htmlFor="login-password">
              <input
                id="login-password"
                type="password"
                required
                autoComplete="current-password"
                placeholder={t("auth.login.passwordPlaceholder")}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>

            <button type="submit" className="cta-button auth-button" disabled={mutation.isPending}>
              {mutation.isPending ? t("auth.login.submitting") : t("auth.login.submit")}
            </button>
          </form>

          <div className="auth-links">
            <p>
              {t("auth.login.noAccount")} <Link to="/register">{t("auth.login.createOne")}</Link>
            </p>
            <p>
              <Link to="/forgot-password">{t("auth.login.forgotPassword")}</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
