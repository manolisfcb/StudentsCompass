import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { FormField } from "@/components/patterns/FormField";
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
    <PageScope name="company-dashboard" className="dashboard-container">
      <DocumentMeta
        title={t("company.postings.seoTitle")}
        description={t("company.postings.seoDescription")}
        path="/company/postings"
      />
      <section className="section-card">
        <div className="section-card-head">
          <div>
            <h3>{t("company.postings.title")}</h3>
          </div>
          <button type="button" className="btn btn-primary" onClick={() => setCreating((value) => !value)}>
            {creating ? t("company.postings.cancel") : t("company.postings.newPosting")}
          </button>
        </div>

        {creating ? <JobPostingForm onDone={() => setCreating(false)} /> : null}

        <AsyncBoundary query={query}>
          {(postings) =>
            postings.length === 0 ? (
              <div className="empty-state">
                <p>{t("company.postings.empty")}</p>
              </div>
            ) : (
              <ul className="job-list">
                {postings.map((posting) => (
                  <PostingRow key={posting.id} posting={posting} />
                ))}
              </ul>
            )
          }
        </AsyncBoundary>
      </section>
    </PageScope>
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
      <li className="job-item">
        <JobPostingForm posting={posting} onDone={() => setEditing(false)} />
      </li>
    );
  }

  return (
    <li className="job-item">
      <div>
        <div className="job-title">{posting.title}</div>
        <div className="job-info">{posting.location ?? t("company.postings.noLocation")}</div>
        <span className={`status-pill ${posting.is_active ? "active" : "inactive"}`}>
          {posting.is_active ? t("company.postings.active") : t("company.postings.inactive")}
        </span>
      </div>
      <div className="action-buttons">
        <button type="button" className="btn btn-secondary" onClick={() => setEditing(true)}>
          {t("company.postings.edit")}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={toggleActiveMutation.isPending}
          onClick={() => toggleActiveMutation.mutate()}
        >
          {posting.is_active ? t("company.postings.deactivate") : t("company.postings.activate")}
        </button>
        <button
          type="button"
          className="btn btn-danger"
          disabled={deleteMutation.isPending}
          onClick={() => {
            if (window.confirm(t("company.postings.confirmDelete"))) deleteMutation.mutate();
          }}
        >
          {t("company.postings.delete")}
        </button>
      </div>
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
    <form onSubmit={handleSubmit} className="recruiter-form">
      {mutation.isError ? (
        <p className="feedback-message" role="alert">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("company.postings.saveError")}
        </p>
      ) : null}
      <div className="recruiter-form-grid">
        <FormField label={t("company.postings.form.title")}>
          <input required value={title} onChange={(e) => setTitle(e.target.value)} />
        </FormField>
        <FormField label={t("company.postings.form.location")}>
          <input value={location} onChange={(e) => setLocation(e.target.value)} />
        </FormField>
        <FormField label={t("company.postings.form.jobType")}>
          <input value={jobType} onChange={(e) => setJobType(e.target.value)} />
        </FormField>
        <FormField className="form-field full" label={t("company.postings.form.description")}>
          <textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
        </FormField>
      </div>
      <div className="recruiter-actions">
        <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("company.postings.saving") : t("company.postings.save")}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onDone}>
          {t("company.postings.cancel")}
        </button>
      </div>
    </form>
  );
}
