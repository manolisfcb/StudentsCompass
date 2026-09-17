import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button, FormField, Input, SectionHeader, Select } from "@/components/ui";
import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { type Profile, updateProfile } from "@/features/profile-resumes/api";

const SEX_OPTIONS = ["Female", "Male", "Non-binary", "Prefer not to say"] as const;

/**
 * Personal details (`userProfile.html`'s `#profileForm`). Only the fields a
 * person may edit about themself: `is_active`/`is_superuser`/`is_verified`
 * live on the same `UserUpdate` schema but are never in this form, and
 * fastapi-users' `safe=True` self-update path strips them server-side even if
 * a caller sent them — this form simply never offers to.
 */
export function ProfileForm({ profile }: { profile: Profile }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [firstName, setFirstName] = useState(profile.first_name ?? "");
  const [lastName, setLastName] = useState(profile.last_name ?? "");
  const [nickname, setNickname] = useState(profile.nickname ?? "");
  const [phone, setPhone] = useState(profile.phone ?? "");
  const [sex, setSex] = useState(profile.sex ?? "");
  const [age, setAge] = useState(profile.age?.toString() ?? "");
  const [address, setAddress] = useState(profile.address ?? "");

  const mutation = useMutation({
    mutationFn: () =>
      updateProfile({
        first_name: firstName || null,
        last_name: lastName || null,
        nickname: nickname || null,
        phone: phone || null,
        sex: sex || null,
        age: age === "" ? null : Number(age),
        address: address || null,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.profile.current, updated);
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.reset();
    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <SectionHeader title={t("profile.form.title")} description={t("profile.form.intro")} />

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("profile.form.firstName")}>
          <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        </FormField>
        <FormField label={t("profile.form.lastName")}>
          <Input value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </FormField>
        <FormField label={t("profile.form.nickname")}>
          <Input value={nickname} onChange={(e) => setNickname(e.target.value)} />
        </FormField>
        <FormField label={t("profile.form.email")}>
          <Input value={profile.email} disabled />
        </FormField>
        <FormField label={t("profile.form.phone")}>
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </FormField>
        <FormField label={t("profile.form.age")}>
          <Input type="number" min={0} value={age} onChange={(e) => setAge(e.target.value)} />
        </FormField>
        <FormField label={t("profile.form.sex")}>
          <Select value={sex} onChange={(e) => setSex(e.target.value)}>
            <option value="">{t("profile.form.sexUnset")}</option>
            {SEX_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField
          className="sm:col-span-2"
          label={t("profile.form.address")}
          hint={t("profile.form.addressHint")}
        >
          <Input value={address} onChange={(e) => setAddress(e.target.value)} />
        </FormField>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
        {/* The status sits next to the button it reports on, and carries the
          * tone of what happened — a save failure that reads like a save
          * confirmation is the one thing this line must not do. */}
        <p
          role="status"
          className={
            mutation.isError ? "mr-auto text-body-sm text-danger" : "mr-auto text-body-sm text-success"
          }
        >
          {mutation.isError
            ? mutation.error instanceof ApiError && mutation.error.detail
              ? mutation.error.detail.message
              : t("profile.form.error")
            : mutation.isSuccess
              ? t("profile.form.success")
              : null}
        </p>
        <Button type="submit" loading={mutation.isPending}>
          {mutation.isPending ? t("profile.form.saving") : t("profile.form.save")}
        </Button>
      </div>
    </form>
  );
}
