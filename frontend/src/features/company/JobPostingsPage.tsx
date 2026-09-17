import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Alert, Badge, Button, Card, EmptyState, FormField, Input, PageHeader, Textarea } from "@/components/ui";
import {
  createJobPosting,
  deleteJobPosting,
  fetchJobPostings,
  updateJobPosting,
  type JobPosting,
  type JobPostingCreate,
} from "@/features/company/api";

const QUERY_KEY = ["company", "job-postings"];

/** The job-posting CRUD, on its own screen. */
export function JobPostingsPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: QUERY_KEY, queryFn: fetchJobPostings });
  const [creating, setCreating] = useState(false);

  return (
    <div className="flex flex-col gap-6">
      <DocumentMeta
        title={t("company.postings.seoTitle")}
        description={t("company.postings.seoDescription")}
        path="/company/postings"
      />

      <PageHeader
        title={t("company.postings.title")}
        actions={
          <Button variant={creating ? "outline" : "primary"} onClick={() => setCreating((value) => !value)}>
            {creating ? t("company.postings.cancel") : t("company.postings.newPosting")}
          </Button>
        }
      />

      {creating ? (
        <Card>
          <JobPostingForm onDone={() => setCreating(false)} />
        </Card>
      ) : null}

      <AsyncBoundary query={query}>
        {(postings) =>
          postings.length === 0 ? (
            <EmptyState title={t("company.postings.empty")} icon="🏗️" />
          ) : (
            <ul className="flex flex-col gap-3">
              {postings.map((posting) => (
                <PostingRow key={posting.id} posting={posting} />
              ))}
            </ul>
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
    return (
      <li>
        <Card>
          <JobPostingForm posting={posting} onDone={() => setEditing(false)} />
        </Card>
      </li>
    );
  }

  return (
    <li>
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-card-title text-ink">{posting.title}</p>
            <Badge tone={posting.is_active ? "success" : "neutral"}>
              {posting.is_active ? t("company.postings.active") : t("company.postings.inactive")}
            </Badge>
          </div>
          <p className="mt-0.5 text-caption text-ink-muted">
            {posting.location ?? t("company.postings.noLocation")}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            {t("company.postings.edit")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            loading={toggleActiveMutation.isPending}
            onClick={() => toggleActiveMutation.mutate()}
          >
            {posting.is_active ? t("company.postings.deactivate") : t("company.postings.activate")}
          </Button>
          <Button
            variant="danger"
            size="sm"
            loading={deleteMutation.isPending}
            onClick={() => {
              if (window.confirm(t("company.postings.confirmDelete"))) deleteMutation.mutate();
            }}
          >
            {t("company.postings.delete")}
          </Button>
        </div>
      </Card>
    </li>
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
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("company.postings.saveError")}
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("company.postings.form.title")} required>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </FormField>
        <FormField label={t("company.postings.form.location")}>
          <Input value={location} onChange={(e) => setLocation(e.target.value)} />
        </FormField>
        <FormField label={t("company.postings.form.jobType")}>
          <Input value={jobType} onChange={(e) => setJobType(e.target.value)} />
        </FormField>
        <FormField label={t("company.postings.form.description")} className="sm:col-span-2">
          <Textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
        </FormField>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" loading={mutation.isPending}>
          {mutation.isPending ? t("company.postings.saving") : t("company.postings.save")}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t("company.postings.cancel")}
        </Button>
      </div>
    </form>
  );
}
