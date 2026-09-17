import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useRef } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { type Column, DataTable, Button } from "@/components/ui";
import { FilePicker } from "@/features/profile-resumes/FilePicker";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { deleteResume, fetchResumes, type Resume, uploadResume } from "@/features/profile-resumes/api";

const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx"];

/**
 * CV upload + list + delete (`userProfile.html`'s upload widget and table).
 *
 * The filename is rendered through `DataTable`'s cell function, which returns
 * a React node built with plain JSX text — never `dangerouslySetInnerHTML` —
 * so a filename cannot become markup (F-03).
 */
export function ResumeList() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.resumes.list, queryFn: fetchResumes });

  return (
    <>
      <h3>{t("profile.resumes.title")}</h3>
      <UploadControl />
      <AsyncBoundary query={query}>{(resumes) => <ResumeTable resumes={resumes} />}</AsyncBoundary>
    </>
  );
}

function UploadControl() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: uploadResume,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.resumes.list });
      if (inputRef.current) inputRef.current.value = "";
    },
  });

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    mutation.reset();
    mutation.mutate(file);
  }

  return (
    <div className="flex flex-col gap-2">
      <FilePicker
        title={t("profile.resumes.uploadLabel")}
        hint={t("profile.resumes.uploadHint")}
        buttonLabel={mutation.isPending ? t("profile.resumes.uploading") : t("profile.resumes.chooseFile")}
        accept={ALLOWED_EXTENSIONS.join(",")}
        inputRef={inputRef}
        busy={mutation.isPending}
        onChange={handleChange}
      />
      {mutation.isError ? (
        <p role="alert" className="text-caption text-danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("profile.resumes.uploadError")}
        </p>
      ) : null}
    </div>
  );
}

function ResumeTable({ resumes }: { resumes: Resume[] }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: deleteResume,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.resumes.list });
    },
  });

  const columns: Column<Resume>[] = [
    {
      key: "name",
      header: t("profile.resumes.columnFile"),
      cell: (resume) => <span>{resume.original_filename}</span>,
    },
    {
      key: "view",
      header: t("profile.resumes.columnView"),
      cell: (resume) =>
        isHttpUrl(resume.view_url) ? (
          <a
            href={resume.view_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-primary hover:text-primary-hover"
          >
            {t("profile.resumes.view")}
          </a>
        ) : null,
    },
    {
      key: "actions",
      header: t("profile.resumes.columnActions"),
      cell: (resume) => (
        <Button
          variant="ghost"
          size="sm"
          disabled={mutation.isPending && mutation.variables === resume.id}
          onClick={() => mutation.mutate(resume.id)}
        >
          {t("profile.resumes.delete")}
        </Button>
      ),
    },
  ];

  return (
    <>
      {mutation.isError ? (
        <p role="alert" className="mb-2 text-caption text-danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("profile.resumes.deleteError")}
        </p>
      ) : null}
      <DataTable
        rows={resumes}
        columns={columns}
        rowKey={(resume) => resume.id}
        caption={t("profile.resumes.title")}
        empty={{ title: t("profile.resumes.empty") }}
      />
    </>
  );
}

/** Same allowlist the legacy `SafeDom.link` helper enforced (F-03). */
function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value, window.location.origin);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}
