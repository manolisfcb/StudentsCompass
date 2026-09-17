import { useMutation } from "@tanstack/react-query";
import { type ChangeEvent, type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { FormField } from "@/components/patterns/FormField";
import {
  type AdminResourceCreate,
  type AdminResourceDetail,
  uploadAdminResourceFile,
} from "@/features/admin/api";

type ModuleInput = NonNullable<AdminResourceCreate["modules"]>[number];
type LessonInput = NonNullable<ModuleInput["lessons"]>[number];
type LessonDraft = LessonInput & { key: string };
type ModuleDraft = Omit<ModuleInput, "lessons"> & { key: string; lessons: LessonDraft[] };

function key(): string {
  return crypto.randomUUID();
}

function emptyLesson(): LessonDraft {
  return { key: key(), title: "", content_type: "text", content: "" };
}

function emptyModule(): ModuleDraft {
  return { key: key(), title: "", description: null, lessons: [emptyLesson()] };
}

function initialModules(resource?: AdminResourceDetail): ModuleDraft[] {
  return (resource?.modules ?? []).map((module) => ({
    key: module.id,
    title: module.title,
    description: module.description ?? null,
    lessons: (module.lessons ?? []).map((lesson) => ({
      key: lesson.id,
      title: lesson.title,
      content_type: lesson.content_type,
      content: lesson.content ?? "",
      video_url: lesson.video_url ?? null,
      resource_url: lesson.resource_url ?? null,
      notes: lesson.notes ?? null,
      reading_time_minutes: lesson.reading_time_minutes ?? null,
    })),
  }));
}

export function ResourceEditor({
  resource,
  onSave,
  onCancel,
}: {
  resource?: AdminResourceDetail;
  onSave: (payload: AdminResourceCreate) => Promise<void>;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [title, setTitle] = useState(resource?.title ?? "");
  const [description, setDescription] = useState(resource?.description ?? "");
  const [category, setCategory] = useState(resource?.category ?? "");
  const [level, setLevel] = useState(resource?.level ?? "");
  const [icon, setIcon] = useState(resource?.icon ?? "");
  const [duration, setDuration] = useState(resource?.estimated_duration_minutes?.toString() ?? "");
  const [externalUrl, setExternalUrl] = useState(resource?.external_url ?? "");
  const [tags, setTags] = useState((resource?.tags ?? []).join(", "));
  const [published, setPublished] = useState(resource?.is_published ?? true);
  const [locked, setLocked] = useState(resource?.is_locked ?? false);
  const [modules, setModules] = useState<ModuleDraft[]>(() => initialModules(resource));

  const save = useMutation({ mutationFn: onSave });

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  function updateModule(moduleKey: string, patch: Partial<ModuleDraft>) {
    setModules((current) => current.map((module) => (module.key === moduleKey ? { ...module, ...patch } : module)));
  }

  function updateLesson(moduleKey: string, lessonKey: string, patch: Partial<LessonDraft>) {
    setModules((current) =>
      current.map((module) =>
        module.key === moduleKey
          ? {
              ...module,
              lessons: (module.lessons ?? []).map((lesson) =>
                lesson.key === lessonKey ? { ...lesson, ...patch } : lesson,
              ),
            }
          : module,
      ),
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({
      title,
      description,
      category,
      level: level || null,
      icon: icon || null,
      estimated_duration_minutes: duration ? Number(duration) : null,
      external_url: externalUrl || null,
      tags: tags.split(",").map((value) => value.trim()).filter(Boolean),
      is_published: published,
      is_locked: locked,
      modules: modules.map((module) => ({
        title: module.title,
        description: module.description ?? null,
        lessons: module.lessons.map((lesson) => ({
          title: lesson.title,
          content_type: lesson.content_type,
          content: lesson.content ?? null,
          video_url: lesson.video_url ?? null,
          resource_url: lesson.resource_url ?? null,
          notes: lesson.notes ?? null,
          reading_time_minutes: lesson.reading_time_minutes ?? null,
        })),
      })),
    });
  }

  return (
    <div className="admin-modal-overlay" role="dialog" aria-modal="true">
      <form onSubmit={submit} className="admin-modal resource-create-modal">
        <div className="admin-modal-title">
          {resource ? t("admin.resources.editor.editTitle") : t("admin.resources.editor.createTitle")}
        </div>
        <div className="admin-modal-desc">{t("admin.resources.editor.description")}</div>

        {save.isError ? (
          <p className="admin-login-error visible" role="alert">
            {save.error instanceof ApiError && save.error.detail
              ? save.error.detail.message
              : t("admin.resources.editor.saveError")}
          </p>
        ) : null}

        <div className="admin-form-row">
          <FormField className="admin-form-group" label={t("admin.resources.editor.title")}>
            <input required value={title} onChange={(e) => setTitle(e.target.value)} />
          </FormField>
          <FormField className="admin-form-group" label={t("admin.resources.editor.category")}>
            <input required value={category} onChange={(e) => setCategory(e.target.value)} />
          </FormField>
        </div>
        <FormField className="admin-form-group" label={t("admin.resources.editor.resourceDescription")}>
          <textarea required rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        </FormField>
        <div className="admin-form-row">
          <FormField className="admin-form-group" label={t("admin.resources.editor.level")}>
            <input value={level} onChange={(e) => setLevel(e.target.value)} />
          </FormField>
          <FormField className="admin-form-group" label={t("admin.resources.editor.icon")}>
            <input value={icon} onChange={(e) => setIcon(e.target.value)} />
          </FormField>
          <FormField className="admin-form-group" label={t("admin.resources.editor.duration")}>
            <input min="0" type="number" value={duration} onChange={(e) => setDuration(e.target.value)} />
          </FormField>
        </div>
        <FormField className="admin-form-group" label={t("admin.resources.editor.externalUrl")}>
          <input type="url" value={externalUrl} onChange={(e) => setExternalUrl(e.target.value)} />
        </FormField>
        <FormField className="admin-form-group" label={t("admin.resources.editor.tags")}>
          <input value={tags} onChange={(e) => setTags(e.target.value)} />
        </FormField>
        <div className="admin-form-row">
          <label className="admin-form-checkbox">
            <input type="checkbox" checked={published} onChange={(e) => setPublished(e.target.checked)} />
            {t("admin.resources.editor.published")}
          </label>
          <label className="admin-form-checkbox">
            <input type="checkbox" checked={locked} onChange={(e) => setLocked(e.target.checked)} />
            {t("admin.resources.editor.locked")}
          </label>
        </div>

        <section className="resource-structure">
          <div className="resource-structure-header">
            <h4 className="resource-structure-title">{t("admin.resources.editor.structure")}</h4>
            <button
              type="button"
              className="admin-btn admin-btn-ghost"
              onClick={() => setModules((current) => [...current, emptyModule()])}
            >
              {t("admin.resources.editor.addModule")}
            </button>
          </div>
          {modules.map((module, moduleIndex) => (
            <article key={module.key} className="resource-module-block">
              <div className="resource-module-head">
                <strong>{t("admin.resources.editor.module", { number: moduleIndex + 1 })}</strong>
                <button
                  type="button"
                  className="admin-btn admin-btn-ghost"
                  onClick={() => setModules((current) => current.filter((item) => item.key !== module.key))}
                >
                  {t("admin.resources.editor.remove")}
                </button>
              </div>
              <input
                required
                className="admin-form-input"
                aria-label={t("admin.resources.editor.moduleTitle")}
                value={module.title}
                onChange={(e) => updateModule(module.key, { title: e.target.value })}
              />
              <textarea
                className="admin-form-input"
                aria-label={t("admin.resources.editor.moduleDescription")}
                value={module.description ?? ""}
                onChange={(e) => updateModule(module.key, { description: e.target.value || null })}
              />
              <div className="resource-lesson-list">
                {(module.lessons ?? []).map((lesson, lessonIndex) => (
                  <LessonRow
                    key={lesson.key}
                    lesson={lesson}
                    number={lessonIndex + 1}
                    onChange={(patch) => updateLesson(module.key, lesson.key, patch)}
                    onRemove={() =>
                      updateModule(module.key, {
                        lessons: (module.lessons ?? []).filter((item) => item.key !== lesson.key),
                      })
                    }
                  />
                ))}
              </div>
              <button
                type="button"
                className="admin-btn admin-btn-ghost"
                onClick={() => updateModule(module.key, { lessons: [...(module.lessons ?? []), emptyLesson()] })}
              >
                {t("admin.resources.editor.addLesson")}
              </button>
            </article>
          ))}
        </section>

        <div className="admin-modal-actions">
          <button type="button" className="admin-btn admin-btn-ghost" onClick={onCancel}>
            {t("admin.resources.editor.cancel")}
          </button>
          <button type="submit" className="admin-btn admin-btn-primary" disabled={save.isPending}>
            {save.isPending ? t("admin.resources.editor.saving") : t("admin.resources.editor.save")}
          </button>
        </div>
      </form>
    </div>
  );
}

function LessonRow({
  lesson,
  number,
  onChange,
  onRemove,
}: {
  lesson: LessonDraft;
  number: number;
  onChange: (patch: Partial<LessonDraft>) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const upload = useMutation({
    mutationFn: uploadAdminResourceFile,
    onSuccess: (file) => onChange({ resource_url: file.file_url, content_type: file.content_type }),
  });

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) upload.mutate(file);
  }

  return (
    <div className="resource-lesson-block">
      <div className="resource-module-head">
        <strong>{t("admin.resources.editor.lesson", { number })}</strong>
        <button type="button" className="admin-btn admin-btn-ghost" onClick={onRemove}>
          {t("admin.resources.editor.remove")}
        </button>
      </div>
      <div className="admin-form-row">
        <input
          required
          className="admin-form-input"
          aria-label={t("admin.resources.editor.lessonTitle")}
          value={lesson.title}
          onChange={(e) => onChange({ title: e.target.value })}
        />
        <input
          className="admin-form-input"
          aria-label={t("admin.resources.editor.lessonType")}
          list={`admin-lesson-types-${lesson.key}`}
          value={lesson.content_type}
          onChange={(e) => onChange({ content_type: e.target.value })}
        />
      </div>
      <textarea
        className="admin-form-input"
        aria-label={t("admin.resources.editor.lessonContent")}
        value={lesson.content ?? ""}
        onChange={(e) => onChange({ content: e.target.value })}
      />
      <div className="admin-form-row">
        <input
          className="admin-form-input"
          aria-label={t("admin.resources.editor.resourceUrl")}
          value={lesson.resource_url ?? ""}
          onChange={(e) => onChange({ resource_url: e.target.value || null })}
        />
        <label className="admin-upload-label">
          {upload.isPending ? t("admin.resources.editor.uploading") : t("admin.resources.editor.upload")}
          <input type="file" className="sr-only" disabled={upload.isPending} onChange={chooseFile} />
        </label>
      </div>
      {upload.isError ? (
        <p className="admin-login-error visible" role="alert">
          {t("admin.resources.editor.uploadError")}
        </p>
      ) : null}
      <datalist id={`admin-lesson-types-${lesson.key}`}>
        {[
          "text",
          "html",
          "external_link",
          "pdf_url",
          "ppt_url",
          "video_url",
          "resume_upload",
        ].map((value) => <option key={value} value={value} />)}
      </datalist>
    </div>
  );
}
