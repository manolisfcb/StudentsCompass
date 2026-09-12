import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  type ActorKind,
  describeAuthError,
  registerCompany,
  registerStudent,
} from "@/features/auth/api";
import { AccountTypeToggle, AsidePoint, Field, INPUT_CLASS } from "@/features/auth/formParts";

const MIN_PASSWORD_LENGTH = 8;
/** How long the success message shows before redirecting, matching the legacy page. */
const REDIRECT_DELAY_MS = 2000;

export function RegisterPage() {
  const { t } = useTranslation();
  const [kind, setKind] = useState<ActorKind>("student");

  return (
    <div className="mx-auto grid max-w-4xl gap-10 md:grid-cols-2 md:items-center">
      <DocumentMeta
        title={t("auth.register.title")}
        description={t("auth.register.seoDescription")}
        path="/register"
      />

      <aside className="auth-aside-gradient space-y-6 rounded-3xl p-8 text-white shadow-[0_32px_80px_rgba(15,23,42,0.24)]">
        <span className="inline-block rounded-full border border-white/30 bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-wide text-white">
          {t("auth.register.kicker")}
        </span>
        <h1 className="text-3xl font-bold text-white">{t("auth.register.heroTitle")}</h1>
        <p className="text-white/85">{t("auth.register.heroBody")}</p>
        <div className="space-y-3">
          <AsidePoint icon="🎯" title={t("auth.register.point1.title")} body={t("auth.register.point1.body")} tone="dark" />
          <AsidePoint icon="🏢" title={t("auth.register.point2.title")} body={t("auth.register.point2.body")} tone="dark" />
        </div>
      </aside>

      <div className="rounded-3xl border border-border bg-surface p-6 shadow-[0_24px_60px_rgba(15,23,42,0.12)]">
        <Link to="/" className="text-sm text-ink-soft hover:text-brand">
          {t("auth.backToHome")}
        </Link>
        <h2 className="mt-4 text-2xl font-semibold text-ink">{t("auth.register.title")}</h2>
        <p className="mt-1 text-sm text-ink-soft">{t("auth.register.subtitle")}</p>

        <div className="mt-6">
          <AccountTypeToggle value={kind} onChange={setKind} />
        </div>

        <div className="mt-4">{kind === "student" ? <StudentForm /> : <CompanyForm />}</div>

        <p className="mt-6 text-sm text-ink-soft">
          {t("auth.register.haveAccount")}{" "}
          <Link to="/login" className="text-brand hover:underline">
            {t("auth.register.login")}
          </Link>
        </p>
      </div>
    </div>
  );
}

/** Same rule the legacy `register.js` enforced client-side before the request. */
function validatePasswords(
  password: string,
  confirmPassword: string,
  t: (key: string) => string,
): string | null {
  if (password !== confirmPassword) return t("auth.register.error.passwordMismatch");
  if (password.length < MIN_PASSWORD_LENGTH) return t("auth.register.error.passwordTooShort");
  return null;
}

function useRedirectAfterSuccess(active: boolean) {
  const navigate = useNavigate();
  useEffect(() => {
    if (!active) return;
    const timer = window.setTimeout(() => navigate("/login"), REDIRECT_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [active, navigate]);
}

function StudentForm() {
  const { t } = useTranslation();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [nickname, setNickname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      registerStudent({
        first_name: firstName,
        last_name: lastName,
        nickname,
        email,
        password,
        is_active: true,
        is_superuser: false,
        is_verified: false,
      }),
  });

  useRedirectAfterSuccess(mutation.isSuccess);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const error = validatePasswords(password, confirmPassword, t);
    setValidationError(error);
    if (error) return;
    mutation.reset();
    mutation.mutate();
  }

  const errorMessage = validationError ?? (mutation.isError ? describeAuthError(mutation.error, t) : null);

  return (
    <form className="space-y-4" onSubmit={handleSubmit} noValidate>
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {mutation.isSuccess ? <Alert tone="success">{t("auth.register.success.student")}</Alert> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("auth.register.student.firstName")}>
          <input
            required
            autoComplete="given-name"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
        <Field label={t("auth.register.student.lastName")}>
          <input
            required
            autoComplete="family-name"
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>

      <Field label={t("auth.register.student.nickname")}>
        <input
          required
          placeholder={t("auth.register.student.nicknamePlaceholder")}
          value={nickname}
          onChange={(event) => setNickname(event.target.value)}
          className={INPUT_CLASS}
        />
      </Field>

      <Field label={t("auth.register.student.email")}>
        <input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className={INPUT_CLASS}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("auth.register.student.password")}>
          <input
            type="password"
            required
            autoComplete="new-password"
            placeholder={t("auth.register.student.passwordPlaceholder")}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
        <Field label={t("auth.register.student.confirmPassword")}>
          <input
            type="password"
            required
            autoComplete="new-password"
            placeholder={t("auth.register.student.confirmPasswordPlaceholder")}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>

      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? t("auth.register.submitting") : t("auth.register.student.submit")}
      </Button>
    </form>
  );
}

function CompanyForm() {
  const { t } = useTranslation();
  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState("");
  const [contactPerson, setContactPerson] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [website, setWebsite] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      registerCompany({
        company_name: companyName,
        industry: industry || null,
        contact_person: contactPerson || null,
        email,
        phone: phone || null,
        website: website || null,
        location: location || null,
        description: description || null,
        password,
      }),
  });

  useRedirectAfterSuccess(mutation.isSuccess);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const error = validatePasswords(password, confirmPassword, t);
    setValidationError(error);
    if (error) return;
    mutation.reset();
    mutation.mutate();
  }

  const errorMessage = validationError ?? (mutation.isError ? describeAuthError(mutation.error, t) : null);

  return (
    <form className="space-y-4" onSubmit={handleSubmit} noValidate>
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {mutation.isSuccess ? <Alert tone="success">{t("auth.register.success.company")}</Alert> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("auth.register.company.name")}>
          <input
            required
            value={companyName}
            onChange={(event) => setCompanyName(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
        <Field label={t("auth.register.company.industry")}>
          <input value={industry} onChange={(event) => setIndustry(event.target.value)} className={INPUT_CLASS} />
        </Field>
      </div>

      <Field label={t("auth.register.company.contactPerson")}>
        <input
          value={contactPerson}
          onChange={(event) => setContactPerson(event.target.value)}
          className={INPUT_CLASS}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("auth.register.company.email")}>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
        <Field label={t("auth.register.company.phone")}>
          <input
            type="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("auth.register.company.website")}>
          <input
            type="url"
            value={website}
            onChange={(event) => setWebsite(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
        <Field label={t("auth.register.company.location")}>
          <input
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>

      <Field label={t("auth.register.company.description")}>
        <textarea
          rows={5}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className={INPUT_CLASS}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("auth.register.company.password")}>
          <input
            type="password"
            required
            autoComplete="new-password"
            placeholder={t("auth.register.student.passwordPlaceholder")}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
        <Field label={t("auth.register.company.confirmPassword")}>
          <input
            type="password"
            required
            autoComplete="new-password"
            placeholder={t("auth.register.student.confirmPasswordPlaceholder")}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>

      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? t("auth.register.submitting") : t("auth.register.company.submit")}
      </Button>
    </form>
  );
}
