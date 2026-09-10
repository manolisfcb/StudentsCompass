import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { homePathFor } from "@/app/routes";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { type ActorKind, describeAuthError, login } from "@/features/auth/api";
import { AccountTypeToggle, AsidePoint, Field, INPUT_CLASS } from "@/features/auth/formParts";

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
    <div className="mx-auto grid max-w-4xl gap-10 md:grid-cols-2 md:items-center">
      <DocumentMeta title={t("auth.login.title")} description={t("auth.login.seoDescription")} path="/login" />

      <aside className="space-y-6">
        <span className="text-sm font-semibold uppercase tracking-wide text-brand">
          {t("auth.login.kicker")}
        </span>
        <h1 className="text-3xl font-bold text-ink">{t("auth.login.heroTitle")}</h1>
        <p className="text-ink-soft">{t("auth.login.heroBody")}</p>
        <div className="space-y-4">
          <AsidePoint icon="🧭" title={t("auth.login.point1.title")} body={t("auth.login.point1.body")} />
          <AsidePoint icon="⚡" title={t("auth.login.point2.title")} body={t("auth.login.point2.body")} />
        </div>
      </aside>

      <div className="rounded-lg border border-border bg-surface p-6 shadow-sm">
        <Link to="/" className="text-sm text-ink-soft hover:text-brand">
          {t("auth.backToHome")}
        </Link>
        <h2 className="mt-4 text-2xl font-semibold text-ink">{t("auth.login.title")}</h2>
        <p className="mt-1 text-sm text-ink-soft">{t("auth.login.subtitle")}</p>

        {mutation.isError ? (
          <div className="mt-4">
            <Alert tone="danger">{describeAuthError(mutation.error, t)}</Alert>
          </div>
        ) : null}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
          <AccountTypeToggle value={kind} onChange={setKind} />

          <Field label={t("auth.login.email")}>
            <input
              type="email"
              required
              autoComplete="email"
              placeholder={t("auth.login.emailPlaceholder")}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>

          <Field label={t("auth.login.password")}>
            <input
              type="password"
              required
              autoComplete="current-password"
              placeholder={t("auth.login.passwordPlaceholder")}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>

          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? t("auth.login.submitting") : t("auth.login.submit")}
          </Button>
        </form>

        <div className="mt-6 space-y-1 text-sm text-ink-soft">
          <p>
            {t("auth.login.noAccount")}{" "}
            <Link to="/register" className="text-brand hover:underline">
              {t("auth.login.createOne")}
            </Link>
          </p>
          <p>
            <Link to="/forgot-password" className="text-brand hover:underline">
              {t("auth.login.forgotPassword")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
