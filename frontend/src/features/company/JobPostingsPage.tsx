import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
import { FormField, INPUT_CLASS } from "@/components/patterns/FormField";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  createJobPosting,
  deleteJobPosting,
  fetchJobPostings,
  updateJobPosting,
  type JobPosting,
  type JobPostingCreate,
} from "@/features/company/api";

const QUERY_KEY = ["company", "job-postings"];

/** `company-dashboard.html`'s job-posting CRUD, split into its own screen. */
export function JobPostingsPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: QUERY_KEY, queryFn: fetchJobPostings });
  const [creating, setCreating] = useState(false);

  return (
    <div className="space-y-6">
      <DocumentMeta
        title={t("company.postings.seoTitle")}
        description={t("company.postings.seoDescription")}
        path="/company/postings"
      />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">{t("company.postings.title")}</h1>
        <Button onClick={() => setCreating((value) => !value)}>
          {creating ? t("company.postings.cancel") : t("company.postings.newPosting")}
        </Button>
      </div>

      {creating ? <JobPostingForm onDone={() => setCreating(false)} /> : null}

      <AsyncBoundary query={query}>
        {(postings) =>
          postings.length === 0 ? (
            <EmptyState title={t("company.postings.empty")} />
          ) : (
            <div className="space-y-3">
              {postings.map((posting) => (
                <PostingRow key={posting.id} posting={posting} />
              ))}
            </div>
          )
        }
      </AsyncBoundary>
    </div>
  );
}

function PostingRow({ posting }: { posting: JobPosting }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);

  const toggleActiveMutation = useMutation({
    mutationFn: () => updateJobPosting(posting.id, { is_active: !posting.is_active }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteJobPosting(posting.id),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  });

  if (editing) {
    return <JobPostingForm posting={posting} onDone={() => setEditing(false)} />;
  }

  return (
    <article className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4">
      <div>
        <p className="font-semibold text-ink">{posting.title}</p>
        <p className="text-sm text-ink-soft">{posting.location ?? t("company.postings.noLocation")}</p>
        <span
          className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
            posting.is_active ? "bg-success/10 text-success" : "bg-border text-ink-muted"
          }`}
        >
          {posting.is_active ? t("company.postings.active") : t("company.postings.inactive")}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={() => setEditing(true)}>
          {t("company.postings.edit")}
        </Button>
        <Button variant="secondary" disabled={toggleActiveMutation.isPending} onClick={() => toggleActiveMutation.mutate()}>
          {posting.is_active ? t("company.postings.deactivate") : t("company.postings.activate")}
        </Button>
        <Button
          variant="danger"
          disabled={deleteMutation.isPending}
          onClick={() => {
            if (window.confirm(t("company.postings.confirmDelete"))) deleteMutation.mutate();
          }}
        >
          {t("company.postings.delete")}
        </Button>
      </div>
    </article>
  );
}

function JobPostingForm({ posting, onDone }: { posting?: JobPosting; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(posting?.title ?? "");
  const [location, setLocation] = useState(posting?.location ?? "");
  const [jobType, setJobType] = useState(posting?.job_type ?? "");
  const [description, setDescription] = useState(posting?.description ?? "");

  const mutation = useMutation({
    mutationFn: () => {
      const payload: JobPostingCreate = {
        title,
        location: location || null,
        job_type: jobType || null,
        description: description || null,
        is_active: posting?.is_active ?? true,
      };
      return posting ? updateJobPosting(posting.id, payload) : createJobPosting(payload);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      onDone();
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-border bg-surface p-4">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("company.postings.saveError")}
        </Alert>
      ) : null}
      <FormField label={t("company.postings.form.title")}>
        <input required value={title} onChange={(e) => setTitle(e.target.value)} className={INPUT_CLASS} />
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("company.postings.form.location")}>
          <input value={location} onChange={(e) => setLocation(e.target.value)} className={INPUT_CLASS} />
        </FormField>
        <FormField label={t("company.postings.form.jobType")}>
          <input value={jobType} onChange={(e) => setJobType(e.target.value)} className={INPUT_CLASS} />
        </FormField>
      </div>
      <FormField label={t("company.postings.form.description")}>
        <textarea
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className={INPUT_CLASS}
        />
      </FormField>
      <div className="flex gap-2">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? t("company.postings.saving") : t("company.postings.save")}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t("company.postings.cancel")}
        </Button>
      </div>
    </form>
  );
}
