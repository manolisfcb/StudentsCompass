import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { homePathFor } from "@/app/routes";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Alert, Button, FormField, Input } from "@/components/ui";
import { type ActorKind, describeAuthError, login } from "@/features/auth/api";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { AccountTypeToggle, AsidePoint } from "@/features/auth/formParts";

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
    <>
      <DocumentMeta title={t("auth.login.title")} description={t("auth.login.seoDescription")} path="/login" />

      <AuthLayout
        kicker={t("auth.login.kicker")}
        heroTitle={t("auth.login.heroTitle")}
        heroBody={t("auth.login.heroBody")}
        points={
          <>
            <AsidePoint icon="compass" title={t("auth.login.point1.title")} body={t("auth.login.point1.body")} />
            <AsidePoint icon="flash" title={t("auth.login.point2.title")} body={t("auth.login.point2.body")} />
          </>
        }
        title={t("auth.login.title")}
        subtitle={t("auth.login.subtitle")}
        footer={
          <>
            <p>
              {t("auth.login.noAccount")}{" "}
              <Link to="/register" className="font-medium text-primary hover:text-primary-hover">
                {t("auth.login.createOne")}
              </Link>
            </p>
            <p>
              <Link to="/forgot-password" className="font-medium text-primary hover:text-primary-hover">
                {t("auth.login.forgotPassword")}
              </Link>
            </p>
          </>
        }
      >
        {mutation.isError ? <Alert tone="danger">{describeAuthError(mutation.error, t)}</Alert> : null}

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <AccountTypeToggle idPrefix="type" name="login-type" value={kind} onChange={setKind} />

          <FormField label={t("auth.login.email")}>
            <Input
              id="login-email"
              type="email"
              required
              autoComplete="email"
              placeholder={t("auth.login.emailPlaceholder")}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </FormField>

          <FormField label={t("auth.login.password")}>
            <Input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              placeholder={t("auth.login.passwordPlaceholder")}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </FormField>

          <Button type="submit" size="lg" block loading={mutation.isPending} className="mt-2">
            {mutation.isPending ? t("auth.login.submitting") : t("auth.login.submit")}
          </Button>
        </form>
      </AuthLayout>
    </>
  );
}
