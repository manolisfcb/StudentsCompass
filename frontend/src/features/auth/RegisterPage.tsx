import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Alert, Button, FormField, Input, Textarea } from "@/components/ui";
import { type ActorKind, describeAuthError, registerCompany, registerStudent } from "@/features/auth/api";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { AccountTypeToggle, AsidePoint } from "@/features/auth/formParts";

const MIN_PASSWORD_LENGTH = 8;
/** How long the success message shows before redirecting, matching the legacy page. */
const REDIRECT_DELAY_MS = 2000;

export function RegisterPage() {
  const { t } = useTranslation();
  const [kind, setKind] = useState<ActorKind>("student");

  return (
    <>
      <DocumentMeta
        title={t("auth.register.title")}
        description={t("auth.register.seoDescription")}
        path="/register"
      />

      <AuthLayout
        kicker={t("auth.register.kicker")}
        heroTitle={t("auth.register.heroTitle")}
        heroBody={t("auth.register.heroBody")}
        points={
          <>
            <AsidePoint icon="🎯" title={t("auth.register.point1.title")} body={t("auth.register.point1.body")} />
            <AsidePoint icon="🏢" title={t("auth.register.point2.title")} body={t("auth.register.point2.body")} />
          </>
        }
        title={t("auth.register.title")}
        subtitle={t("auth.register.subtitle")}
        footer={
          <p>
            {t("auth.register.haveAccount")}{" "}
            <Link to="/login" className="font-medium text-primary hover:text-primary-hover">
              {t("auth.register.login")}
            </Link>
          </p>
        }
      >
        <AccountTypeToggle idPrefix="reg-type" name="account-type" value={kind} onChange={setKind} />
        {kind === "student" ? <StudentForm /> : <CompanyForm />}
      </AuthLayout>
    </>
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
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {mutation.isSuccess ? <Alert tone="success">{t("auth.register.success.student")}</Alert> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("auth.register.student.firstName")}>
          <Input
            required
            autoComplete="given-name"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
          />
        </FormField>
        <FormField label={t("auth.register.student.lastName")}>
          <Input
            required
            autoComplete="family-name"
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
          />
        </FormField>
      </div>

      <FormField label={t("auth.register.student.nickname")}>
        <Input
          required
          placeholder={t("auth.register.student.nicknamePlaceholder")}
          value={nickname}
          onChange={(event) => setNickname(event.target.value)}
        />
      </FormField>

      <FormField label={t("auth.register.student.email")}>
        <Input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </FormField>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("auth.register.student.password")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            placeholder={t("auth.register.student.passwordPlaceholder")}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </FormField>
        <FormField label={t("auth.register.student.confirmPassword")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            placeholder={t("auth.register.student.confirmPasswordPlaceholder")}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
        </FormField>
      </div>

      <Button type="submit" size="lg" block loading={mutation.isPending} className="mt-2">
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
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {mutation.isSuccess ? <Alert tone="success">{t("auth.register.success.company")}</Alert> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("auth.register.company.name")}>
          <Input
            required
            value={companyName}
            onChange={(event) => setCompanyName(event.target.value)}
          />
        </FormField>
        <FormField label={t("auth.register.company.industry")}>
          <Input value={industry} onChange={(event) => setIndustry(event.target.value)} />
        </FormField>
      </div>

      <FormField label={t("auth.register.company.contactPerson")}>
        <Input
          value={contactPerson}
          onChange={(event) => setContactPerson(event.target.value)}
        />
      </FormField>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("auth.register.company.email")}>
          <Input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </FormField>
        <FormField label={t("auth.register.company.phone")}>
          <Input
            type="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
          />
        </FormField>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("auth.register.company.website")}>
          <Input
            type="url"
            value={website}
            onChange={(event) => setWebsite(event.target.value)}
          />
        </FormField>
        <FormField label={t("auth.register.company.location")}>
          <Input
            value={location}
            onChange={(event) => setLocation(event.target.value)}
          />
        </FormField>
      </div>

      <FormField label={t("auth.register.company.description")}>
        <Textarea
          rows={5}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </FormField>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("auth.register.company.password")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            placeholder={t("auth.register.student.passwordPlaceholder")}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </FormField>
        <FormField label={t("auth.register.company.confirmPassword")}>
          <Input
            type="password"
            required
            autoComplete="new-password"
            placeholder={t("auth.register.student.confirmPasswordPlaceholder")}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
        </FormField>
      </div>

      <Button type="submit" size="lg" block loading={mutation.isPending} className="mt-2">
        {mutation.isPending ? t("auth.register.submitting") : t("auth.register.company.submit")}
      </Button>
    </form>
  );
}
